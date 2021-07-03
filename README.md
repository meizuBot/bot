this is only here because I'm dumb and will probably forget how to deploy this.
no help will be given for selfhosting gl

```shell
$ git clone --recurse-submodules https://github.com/reallybadbot/bot
$ cd bot
```
if you forget the `--recurse submodules` then do 
```shell
$ git submodule init
``` 
and you should be all good

# setup:
install python `>=3.9.2`

### create venv
```shell
$ python3.9 -m venv venv
```
activate it (windows)
```shell
$ ./venv/Scripts/activate
```
(linux)
```shell
$ source ./venv/Scripts/activate
```
### install requirements
in venv:
```shell
$ python3.9 -m pip install -U -r requirements.txt
$ cd web
$ python3.9 -m pip install -U -r requirements.txt
```
oh and if yur on linux:
```shell
$ python3.9 -m pip install uvloop
```
speed

### create postgres server
yea google how to install postgres and then run this in psql:
```psql
$ CREATE ROLE botto WITH LOGIN PASSWORD 'secret;
$ CREATE DATABASE badbot OWNER botto;
```

### fill out config.yml
make a copy of config.yml.example and fill it out then remove the `.example` filename ending


## running le botto:
bot is same for dev and prod

make sure to activate venv
```shell
$ python3.9 main.py
```

## for website:
make sure botto is running first or else the ipc server will not work

all of this assumes you are in the venv we created earlier
### dev:
```shell
$ uvicorn web.app:app --reload
```

### prod
this runs with a uvicorn worker under gunicorn cuz why not

also this only works on linux lol (pain)

you should probably use nginx or some proxy 
```shell
$ gunicorn -k uvicorn.workers.UvicornWorker -w 4 --forwarded-allow-ips="10.170.3.217,10.170.3.220" web.app:app
```
then like buy a domain and set a cname record to your vps or smth

# final notes:

have fun

also should probably use docker because idk how to run two scripts at the same time and i dont wanna run bot + webserver in same thread for prod

lmao using docker messes up all these unstructions
you can probably use docker-compose.yml file i will make soon and maybe i will add deployment instructions

gl



