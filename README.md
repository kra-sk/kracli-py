# kra.sk Python command-line client

## Requirements
python3 + pycurl

Install requirements on Debian/Ubuntu:
```bash
apt install -y python3-pycurl
```

## Usage
For usage see command-line help:
```basj
./kracli.py -h
```

## Configuration
You can store your credentials in the login section of a configuration file
which is used for session storage, too.
(default location: $HOME/.kracli.cfg)

Example configuration file:
```ini
[login]
username=YOURUSERNAME
password=YOURPASSWORD
```

