#!/usr/bin/python3
#
# Python command-line client for kra.sk file storage
#
# Requirements: pycurl, json, argparse, configparser, os, sys, signal, base64
#

import pycurl
import json
import argparse
import configparser
import os
import sys
import signal
import base64

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

API = 'https://api.kra.sk/api'
UPLOAD_HOST= 'https://upload.kra.sk'
UPLOAD_PATH= '/upload/'
VERSION='0.2'
storage = {}

def apirequest(path, session_id, data):
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, API + "/" + path)
    rd = {}
    if session_id:
        rd['session_id'] = session_id;
    if data:
        rd['data'] = data;
    c.setopt(c.POSTFIELDS, json.dumps(rd))
    c.setopt(c.HTTPHEADER, ['Content-Type: application/json'])
    c.setopt(c.WRITEDATA, buffer)
    try:
        c.perform()
    except pycurl.error as ex:
        code, msg = ex.args
        print(msg)
        sys.exit(1)
    c.close()
    response = buffer.getvalue()
    try:
        injson = json.loads(response)
    except:
        print(response.decode("utf-8"))
        sys.exit(1)
    return injson

def printret(ret):
    if 'data' in ret:
        print(json.dumps(ret['data'], indent=2))
        return(0)
    if 'msg' in ret:
        print(ret['msg'])
    if 'success' in ret:
        return(0)
    elif 'error' in ret:
        return(2)
    else:
        print(ret)
        return(1)

def get_credentials(config, configfile):
    username = os.getenv('KRAUSER')
    password = os.getenv('KRAPASS')
    if (username is None or username == '' or password is None or password == ''):
        try:
            username = config.get('login','username')
            password = config.get('login', 'password')
        except:
            print("Invalid or missing configuration file: " + configfile)
            sys.exit(1)
    if not username or not password:
        print("Credentials missing: use env KRAUSER KRAPASS or " + configfile)
        sys.exit(1)
    return { "username": username, "password": password }

def get_userinfo(session_id):
    if 'userinfo' in storage:
        return storage["userinfo"]
    else:
        ret = apirequest("user/info", session_id, None)
        if 'data' in ret:
            return ret['data']
        else:
            return None

def login(config, configfile):
    try:
        session_id = config.get('session','id')
    except:
        session_id = None

    needlogin = True
    
    if session_id:
        ret = get_userinfo(session_id)
        if ret == None:
            needlogin = True
        else:
            needlogin = False
            storage["userinfo"] = ret

    if needlogin:
       creds = get_credentials(config, configfile)
       d = {'username': creds['username'], 'password': creds['password']}
       ret = apirequest("user/login", None, d)
       if 'success' in ret and 'session_id' in ret:
           session_id = ret['session_id']
           if not config.has_section('session'):
               config.add_section('session')
           config.set('session','id', session_id)
           with open(configfile, 'w') as configfile:
               config.write(configfile)

    return session_id


def handle_ctrl_c(signal, frame):
    print()
    sys.exit(0)
signal.signal(signal.SIGINT, handle_ctrl_c)

def argstr(a):
    if len(a) == 0:
        raise argparse.ArgumentTypeError("Argument must not be empty")
    return a

def header_function(header_line):
    header_line = header_line.decode('iso-8859-1')
    if ':' not in header_line:
        return
    name, value = header_line.split(':', 1)
    name = name.strip()
    value = value.strip()
    name = name.lower()
    storage['headers'][name] = value

def main():
    parser = argparse.ArgumentParser(
      prog=sys.argv[0],
      formatter_class=argparse.RawDescriptionHelpFormatter,
      description='kra.sk storage client',
      epilog='For editing objects with -e | --edit you can change the following: \n'
      + '-p NEWPARENT | -n NEWNAME | -P PASSWORD | --shared or --no-shared\n\n'
      + 'For copying with -o | --copy IDENT you can specify the following: \n'
      + '-p PARENT | -n NEWNAME | -P CURRENT_PASSWORD | -N NEW_PASSWORD | --shared or --no-shared\n\n'
      + 'For uploading with -u | --upload you can specify the the following: \n'
      + '-p PARENT | -I FILESLOT_IDENT | -T TUS_RESOURCE | -C UPLOAD_CHUNK_MB \n\n'
      + 'You can store your credentials in the login section of a ' 
      + 'configuration file\nwhich is used for session storage, too.\n'
      + '(default location: ' + os.getenv('HOME') + '/.kracli.cfg)\n\n'
      + 'Example configuration file:\n' + '[login]\nusername=YOUR_USERNAME\npassword=YOUR_PASSWORD')
    parser.add_argument('-i', '--config', help='configuration file')
    ex = parser.add_mutually_exclusive_group(required=True)
    ex.add_argument('-l', '--list', action='store_true', help='list files and folders')
    ex.add_argument('-c', '--create', type=argstr, metavar='NAME', help='create folder or fileslot (see --shared, --password)')
    ex.add_argument('-e', '--edit', type=argstr, metavar='IDENT', help='edit object, multiple options')
    ex.add_argument('-o', '--copy', type=argstr, metavar='IDENT', help='copy file, multiple options')
    ex.add_argument('-r', '--remove', type=argstr, metavar='IDENT', help='delete file or folder (see --recursive)')
    ex.add_argument('-d', '--download', type=argstr, metavar='IDENT', help='download file')
    ex.add_argument('-u', '--upload', type=argstr, metavar='PATH_TO_FILE', help='upload file')
    ex.add_argument('-U', '--userinfo', action='store_true', help='show user info')
    ex.add_argument('-O', '--objectinfo', metavar='OBJECT_IDENT', help='show object info')
    ex.add_argument('-V', '--version', action='store_true', help='show version')
    parser.add_argument('-W', '--resume', action='store_true', help='download: resume file download')
    parser.add_argument('-S', '--shared', action=argparse.BooleanOptionalAction, help='create or set/unset object as shared')
    parser.add_argument('-P', '--password', metavar='PASSWORD', help='set file/folder password, use empty string for unset')
    parser.add_argument('-N', '--newpassword', metavar='NEWPASSWORD', help='set file/folder password on copy')
    parser.add_argument('-R', '--recursive', action='store_true', help='delete: delete recursively')
    parser.add_argument('-I', '--ident', metavar='IDENT', help='upload: use pre-existing file ident')
    parser.add_argument('-p', '--parent', metavar='IDENT', help='folder ident to operate on')
    parser.add_argument('-F', '--filter', help='list: filter name (allowed globs: * .)')
    parser.add_argument('-n', '--name', metavar='FILENAME', help='download/upload: store file as this name, edit: new name')
    parser.add_argument('-t', '--type', choices=['file','folder'], help='list: limit to object type')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-C', '--upload_chunk', type=int, default=10, help='upload chunk in MB')
    parser.add_argument('-T', '--upload_resource', help='TUS upload resource')
    args = vars(parser.parse_args())

    credentials = False
    user = None
    password = None
    session = None

    if args['config']:
        configfile = args['config']
    else:
        configfile = os.getenv('HOME') + '/.kracli.cfg'

    config = configparser.ConfigParser()
    config.read(configfile)

    session_id = login(config, configfile)

    if args['userinfo']:
        print(json.dumps(get_userinfo(session_id), indent=2))
        sys.exit()

    if args['list']:
        d = {}
        if args['parent']:
            d['ident'] = args['parent']
        if args['filter']:
            d['filter'] = args['filter']
        if args['type']:
            d['type'] = args['type']
        ret = apirequest('file/list', session_id, d)
        sys.exit(printret(ret))

    if args['objectinfo']:
        ret = apirequest('file/info', session_id, {'ident': args['objectinfo']})
        sys.exit(printret(ret))

    if args['create']:
        d = {}
        d['name'] = args['create']
        if args['parent']:
            d['parent'] = args['parent']
        if not args['type'] or args['type'] == 'folder':
            d['folder'] = True;
        if args['shared'] == True:
            d['shared'] = True;
        else:
            d['shared'] = False;
        if args['password'] and args['password'] != '':
            d['password'] = args['password']
        ret = apirequest('file/create', session_id, d)
        sys.exit(printret(ret))

    if args['copy']:
        d = {}
        d['ident'] = args['copy']
        if args['name']:
            d['name'] = args['name']
        if args['parent']:
            d['parent'] = args['parent']
        if args['shared'] == True:
            d['shared'] = True;
        else:
            d['shared'] = False;
        if args['password'] and args['password'] != '':
            d['password'] = args['password']
        if args['newpassword'] and args['newpassword'] != '':
            d['newpassword'] = args['newpassword']
        ret = apirequest('file/copy', session_id, d)
        sys.exit(printret(ret))

    if args['remove']:
        d = {}
        d['ident'] = args['remove']
        d['recursive'] = False;
        if args['recursive']:
            d['recursive'] = True;
        ret = apirequest('file/delete', session_id, d)
        sys.exit(printret(ret))

    if args['edit']:
        c = False
        d = {}
        d['ident'] = args['edit']
        if args['name']:
            d['name'] = args['name']
            c = True
        if args['parent']:
            d['parent'] = args['parent']
            c = True
        if args['shared'] == True or args['shared'] == False:
            d['shared'] = args['shared']
            c = True
        if args['password'] or args['password'] == '':
            if args['password'] == '':
                d['password'] = None
            else:
                d['password'] = args['password']
            c = True
        if c == False:
            print("Nothing to edit")
            sys.exit(1)
        ret = apirequest('file/update', session_id, d)
        sys.exit(printret(ret))
         
    if args['download']:
        d = {}
        d['ident'] = args['download']
        ret = apirequest('file/download', session_id, d)
        if not 'data' in ret or not 'link' in ret['data']:
            sys.exit(printret(ret))
        if args['name']:
            filename = args['name']
        else:
            filename = os.path.basename(ret['data']['link'])
        c = pycurl.Curl()
        c.setopt(pycurl.URL, ret['data']['link'])
        if args['resume'] and os.path.isfile(filename):
            f = open(filename, "ab")
            c.setopt(pycurl.RESUME_FROM, os.path.getsize(filename))
        else:
            if os.path.exists(filename):
                print('Already exists: ' + filename)
                sys.exit(1)
            f = open(filename, "wb")
        print('Downloading ' + args['download'] + ' as: ' + filename)
        c.setopt(pycurl.WRITEDATA, f)
        c.setopt(pycurl.NOPROGRESS, 0)
        try:
            c.perform()
        except pycurl.error as ex:
            code, msg = ex.args
            print(msg)
            sys.exit(1)
        c.close()

    if args['upload']:
        size = None
        if not args['name']:
            name = os.path.basename(args['upload'])
        else:
            name = args['name']
        try:
            size = os.path.getsize(args['upload'])
        except:
            print('File not found or not accessible')
            sys.exit(2)
        if size == 0: 
            print('File has zero size')
            sys.exit(2)
        if not args['upload_resource']:
            if not args['ident']: 
                d = {}
                if args['parent']:
                    d['parent'] = args['folder']
                d['name'] = name
                d['shared'] = False;
                d['folder'] = False;
                if args['shared'] == True:
                     d['shared'] = True;
                ret = apirequest('file/create', session_id, d)
                if 'success' in ret and 'data' in ret and 'ident' in ret['data']:
                    ident = ret['data']['ident']
                else:
                    sys.exit(printret(ret))
                print('Created ident: ' + ident)
            else:
                ident = args['ident']
            c = pycurl.Curl()
            c.setopt(pycurl.URL, UPLOAD_HOST + UPLOAD_PATH)
            c.setopt(c.HTTPHEADER, [
              'Tus-Resumable: 1.0.0',
              'Upload-Length: ' + str(size),
              'Upload-Metadata: ident ' + str(base64.b64encode(ident.encode('ascii')).decode('ascii'))
            ])
            c.setopt(c.CUSTOMREQUEST, 'POST')
            c.setopt(c.HEADERFUNCTION, header_function)
            storage['headers'] = {}
            try:
                c.perform()
            except pycurl.error as ex:
                code, msg = ex.args
                print(msg)
                print('Error retrieving upload resource')
                print('You can retry upload with: ' + sys.argv[0] + ' -u ' + args['upload'] + ' -I ' + ident)
                sys.exit(1)
            c.close()
            if 'location' in storage['headers']:
                resource = storage['headers']['location'].replace(UPLOAD_PATH, '')
            else:
                print('Error retrieving upload resource')
                print('You can retry upload with: ' + sys.argv[0] + ' -u ' + args['upload'] + ' -I ' + ident)
                sys.exit(1)
        else:
            resource = args['upload_resource']

        c = pycurl.Curl()
        c.setopt(pycurl.URL, UPLOAD_HOST + UPLOAD_PATH + resource)
        c.setopt(c.HTTPHEADER, ['Tus-Resumable: 1.0.0'])
        c.setopt(c.CUSTOMREQUEST, 'HEAD')
        c.setopt(c.HEADERFUNCTION, header_function)
        storage['headers'] = {}
        try:
            c.perform()
        except pycurl.error as ex:
            code, msg = ex.args
            print(msg)
            sys.exit(1)
        c.close()
        if 'upload-offset' in storage['headers'] and 'upload-length' in storage['headers']:
            upload_offset = int(storage['headers']['upload-offset'])
            upload_length = int(storage['headers']['upload-length'])
        else:
            print('File already uploaded or other error')
            sys.exit(1)
        if upload_length != size:
            print('Local file and upload resource differ in size')
            sys.exit(1)

        if (args['upload_chunk'] <= 0):
            upload_offset = 0
            print('Starting whole-file upload')
            print('You can restart chunked upload with:\n' + sys.argv[0] + ' -u ' + args['upload'] + ' -T ' + resource)
        else:
            if upload_offset == 0:
                sstr = 'Starting'
                pstr = ''
            else:
                sstr = 'Resuming'
                pstr = ' from position ' + str(upload_offset)
            print(sstr + ' upload with ' + str(args['upload_chunk']) + "MB chunks" + pstr)
            print('You can resume upload with:\n' + sys.argv[0] + ' -u ' + args['upload'] + ' -T ' + resource)
            print('You can restart upload with:\n' + sys.argv[0] + ' -u ' + args['upload'] + ' -T ' + resource + ' -C 0')

        file = open(args['upload'],'rb')
        while upload_offset != size:
            c = pycurl.Curl()
            c.setopt(pycurl.URL, UPLOAD_HOST + UPLOAD_PATH + resource)
            c.setopt(c.UPLOAD, 1)
            c.setopt(c.HTTPHEADER, [
              'Content-Type: application/offset+octet-stream',
              'Tus-Resumable: 1.0.0',
              'Upload-Offset: ' + str(upload_offset),
            ])
            c.setopt(c.CUSTOMREQUEST, 'PATCH')
            c.setopt(c.HEADERFUNCTION, header_function)
            storage['headers'] = {}
            if (args['upload_chunk'] <= 0):
                c.setopt(c.INFILESIZE, size)
            else:
                file.seek(upload_offset, 0)
                c.setopt(c.INFILESIZE, min(size-upload_offset,args['upload_chunk'] * 1024 * 1024))
                c.setopt(c.READDATA, file)
            try:
                c.perform()
            except pycurl.error as ex:
                code, msg = ex.args
                print(msg)
                sys.exit(1)
            c.close()
            if 'upload-offset' in storage['headers']:
                upload_offset = int(storage['headers']['upload-offset'])
        file.close()
        print('Upload successful')

    if args['version']:
        print(VERSION)
        sys.exit()


if __name__ == "__main__":
    main()
