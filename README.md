# Melda Jupyter

## 1. Building the base (Dockerfile.base)

Use `rocker/r-ubuntu:20.04`

`apt-get update && apt-get upgrade -y` to get the newest stuff.

`apt-get install python3-pip` to install pip.

Install [r2u](https://eddelbuettel.github.io/r2u/):
1. add the repo to apt registry.
2. add eddelbluet repo key to apt registry.
3. pin CRANapt repo to top so that when we’re installing packages with apt, the ones in the CRANapt get selected first.
4. `apt-get update && apt-get upgrade -y` once again to get the latest R packages from the repo we’ve added above.
5. install bspm package by running `Rscript --vanilla -e 'install.packages("bspm", repos="https://cran.r-project.org")'` This has to be done in this fashion, or there's a misconfig somewhere (, which I wasn't able to find out where) and bspm doesn't work.
6. add the line `bspm::enable()` to `/etc/R/Rprofile.site` to enable bspm by default, i.e., apt will be used when `install.package()` is called without needing to enable bspm by hand.
7. Start dbus service with `service dbus start` in [start-jupyter](./start-jupyter) file. dbus is needed for `install.packages()` to be linked to `apt-get` without giving `melda` user access to `apt-get` command itself, which effectively means giving `root` access to `melda`&mdash;since containers are started in privileged mode (see S3 mount section below), that would mean giving root access to the host (AWS EC2 instance in current case) to everyone using melda.io.

Install jupyter:
1. `pip install jupyter==1.0.0`.The `jupyter` package is just a meta-package that installs all the (current) jupyter components.
2. `install.packages('IRkernel')` (R kernel for Jupyter. Python kernel comes as default)
3. `IRkernel::installspec(user=FALSE)` to make the kernel available to Jupyter. `user=FALSE` is there to install it system-wide, not user specific.

Set ENV variables like username or JUPYTER_WORKIDR for use later. A sidenote on this is that if you use, for example, `RUN export username=melda` in your Dockerfile, `username` variable won't be preserved at runtime, i.e., it'll only be useful when building the image. If one wants persistent ENV variables, one needs to use `ENV username=melda` in her Dockerfile.

Add melda user: `useradd $username --create-home --shell /bin/bash --uid 1001 -U`. `--shell /bin/bash` is for convenience, I personally don't fancy working in `/bin/sh`. Giving a set user/group id with `--uid 1001` is for setting file permissions later. `-U` creates a group with the same name as the `$username`, which is `melda`.

Create a folder for melda projects. User files/installed plugins will live there.

Copy our custom scripts 

Copy jupyter config file. See below for modifications (and explanations for those) in sections below.

Install Flask and copy files needed for the version check webservice. See [Custom scripts and Jupyter config](#3-custom-scripts-and-jupyter-config)->get-versions.

Make our custom scripts that are under `$SRC` executable (as `root`).

Change working directory to `$JUPYTER_WORKDIR`, which currently is `/home/melda/project`. This means that whatever you're doing from now on, the directory you're operating on is `$JUPYTER_WORKDIR`, unless specified otherwise. 

**S3 mount:**

Containers need to be started in privileged mode for `s3fs` to be able to mount buckets as folders to system, which is not possible in AWS Fargate; melda.io started her life on Fargate actually, due to this privileged mode/mounting problem, she got switched to ECS.

`apt-get install s3fs -y` to install s3fs.

```bash
s3fs $BUCKET_NAME:/$PROJECT_FOLDER $JUPYTER_WORK_DIR \
		-o dbglevel=debug \
		-o curldbg \
		-o passwd_file=/root/.passwd-s3fs \
		-o umask=0007,uid=1001,gid=1001 \
		-o allow_other
```
`-o dbglevel=debug` and `-o curldbg` are related to log output. `-o passwd_file=/root/.passwd-s3fs` reads the credentials needed to connect to S3 bucket from a file. `-o umask 0007` means give `rwx` permissions to the the owner&group and no permissions for others. `uid/gid=1001` is for `melda` user/group. `-o allow_other` enables file access to non-root users; even though `melda` is the owner of the folder&files, she can’t do anything with the mounted directory&mdash;`allow_other` option is mandatory then.

**SSH connections:**

We want to be able to reach our containers through SSH for debugging purposes. As said in sidenotes below, R kernel outputs are just not there&mdash;when something's wrong with an R package, then, there's not that many ways of knowing what happened. When melda.io UI isn't sufficient, we SSH.

1. `apt-get install openssh-server` to install everything SSH.
2. Permit root login to the container and disable password auth by printing the relevant lines to the end of the sshd config file.  
3. Copy the melda pubkey into the image, whose private key is stored in Bitwarden.
4. Start ssh service by `service ssh start` in [start-jupyter](./start-jupyter) file.

## 2. Package installations (Dockerfile)

Install [top downloaded packages](https://www.r-pkg.org/downloaded) for R.

Install most used data science packages for Python.

The list of installed packages can be enlarged, or shortened, depending on the context. The current list is just a preliminary.

**Sidenotes:**

Python has “wheels,” which are precompiled binaries. To give an example, `pandas` has a wheel, which is just downloaded, no compilation. It has dependencies, like `numpy`, which also has a wheel, and is downloaded in the process.

Using r2u, R’s `devtools` took about 10 seconds to install, which normally takes about 15 minutes to compile, on a powerful server, that is.

Installing an older version of a package in R using `devtools::install_version()`, if there’s C/C++ code involved, takes time as it needs compilation. We can't get around that issue using r2u as it only works for the newest versions of the packages.

---
---

IRkernel seems to silence the package install outputs whether in melda.io or in a notebook, both with `devtools::install_version` and `install.packages()`. This seems to be an issue with IRkernel itself&mdash;it flushes its output to stdout.

## 3. Custom scripts and Jupyter config

### get-versions

A bash script that gets Ubuntu; Python, R, and their installed packages' versions and writes them in a JSON file, which looks like:

```
{
	"Ubuntu": "20.04",
	"Python": {
		"Python": "3.8.10",
		"Flask": "2.2.2",
		...
	},
	"R": {
		"R": "4.2.2",
		"dplyr": "1.0.10",
		...
	}
}
```

**version_check_webservice.py**

A Flask app that listens on port 2310 and runs the `get-versions` script when there is a `GET` request on `/versions` endpoint. The app is started in `start-jupyter` script at runtime.

### set-paths

Gets called by `start-jupyter` script at runtime.

1. `export` Python and R versions to be used as plugin file paths, which look like `Python-3.8.10` and `R-4.2.2`. 
2. create the folders with above names on `$JUPYTER_WORKDIR`, which is a folder named project under `$UHOME`, which is currently `/home/melda`.
3. Add Python and R plugin paths to `.pip/pip.conf` and `/etc/R/Rprofile.site`, respectively. This makes sure that the new packages that are being installed live under our custom plugin paths.
4. Set jupyter notebook working directories for both R and Python.

### start-jupyter

This script is the entrypoint to melda jupyter images, i.e., when you create (run) a container with this image, this script gets run.

1. Start `ssh` and `dbus` services.
2. AWS credentials are set through melda-server and send to the image by exporting them as ENV variables. Get those variables and write them to `/root/.passwd-s3fs`. How the connection itself is done is specified above in S3 mount section.
3. Remove the `/root/.passwd-s3fs` file. We don't need it anymore and it contains sensitive information.
4. Run `set-paths` script.
5. Change the ownership of `$UHOME` and the folders under it to `$username`. Which currently means give `/home/melda/*` ownership to `melda`.
6. Start the `version_check_webservice` app in the background.
7. Start the jupyter notebook.

In steps 6&7, we're exporting variables. That's because we are running these task as `$username` and we've set all the variables under `root` user, which is the default user of the Dockerfile, i.e., when you don't specify as which user you want to do the actions you're doing in the dockerfile with a line like `USER $username`, they all get run as root.

### jupyter_notebook_config,py

Trying to set a token for the notebook server is futile. See [this](https://github.com/jupyterlab/jupyterlab/issues/9070) GitHub issue. 

## 4. How to set the same environment for forks

For python, `pip freeze`?
For R, we may use `sessionInfo()` to get the list of attached libraries and use them to create the environment for the forked project.

## 5. Security

We're filtering traffic for all the inbound ports by IP, using AWS security groups. The only IPs allowed are pgeo-dev/prod servers and access through VPN (currently the wireguard server we're hosting on AWS).

We also have `iptables` rules in place:

```
iptables -P INPUT DROP
iptables -P OUTPUT DROP
```

Drop all input/output by default.

```
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT
```

Allow loopback communications, i.e., the host should be able to talk within itself; internal communications.

```
iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
```

Allow container to talk with the host.

```
iptables -A INPUT -s $PGEO_IPS -j ACCEPT
iptables -A INPUT -s $PGEO_IPS -j ACCEPT
```

Accept all connections, regardless of the port number, from allowed IPs.

```
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED -j ACCEPT
```

Allow established connections. This is necessary for communications of any kind with the outside world.
