#!/usr/bin/env python3

import socket
import os
import stat
import sys
import urllib.parse
import datetime

from threading import Thread
from argparse import ArgumentParser

BUFSIZE = 4096

CRLF = '\r\n'
OK = 'HTTP/1.1 200 OK{}'.format(CRLF)
MOVED_PERMANENTLY = 'HTTP/1.1 301 MOVED PERMANENTLY{}Location:  https://twin-cities.umn.edu{}Connection: close{}{}'.format(CRLF, CRLF, CRLF, CRLF)
FORBIDDEN = 'HTTP/1.1 403 FORBIDDEN{}Connection: close{}{}'.format(CRLF, CRLF, CRLF)
NOT_FOUND = 'HTTP/1.1 404 NOT FOUND{}Connection: close{}{}'.format(CRLF, CRLF, CRLF)
METHOD_NOT_ALLOWED = 'HTTP/1.1 405  METHOD NOT ALLOWED{}Allow: GET, HEAD, POST {}Connection: close{}{}'.format(CRLF, CRLF, CRLF, CRLF)
NOT_ACCEPTABLE = 'HTTP/1.1 406 NOT ACCEPTABLE{}Connection: close{}{}'.format(CRLF, CRLF, CRLF)

# returns the type of the
def get_type(resource):
    if resource[-5:] == '.html':
        return "text/html"
    elif resource[-4:] == '.png':
        return "image/png"
    elif resource[-4:] == '.mp3':
        return "audio/mpeg"
    elif resource[-3:] == '.js':
        return "text/javascript"
    elif resource[-4:] == '.css':
        return "text/css"
    elif resource[-5:] == 'umntc':
        return "*/*"
    
    return ''

# get the contents of the requested file
def get_contents(fname):
    with open(fname, 'rb') as f:
        return f.read()

def check_perms(resource):
    """Returns True if resource has read permissions set on 'others'"""
    stmode = os.stat(resource).st_mode
    return (getattr(stat, 'S_IROTH') & stmode) > 0

# verifies that the requested resource matches the requested accepted types
def check_accept(acceptline, resource):
    ftype = get_type(resource)
    print ("ACCEPT LINE: ", acceptline)

    if (ftype not in acceptline and '*/*' not in acceptline):
        return ''

    return 'ok'

class Server:
    def __init__(self, host, port):
        print('listening on port {}'.format(port))
        self.host = host
        self.port = port

        self.setup_socket()

        self.accept()

        self.sock.shutdown()
        self.sock.close()

    def setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(128)

    def accept(self):
        while True:
          (client, address) = self.sock.accept()
          th = Thread(target=self.accept_request, args=(client, address))
          th.start()

  # accepts a request
    def accept_request(self, client_sock, client_addr):
        print("accept request")
        data = client_sock.recv(BUFSIZE)
        req = data.decode('utf-8') #returns a string
        response=self.process_request(req) #returns a string

        try:
            response = bytes(response, 'utf-8')
        except:
            pass

        client_sock.send(response)

        #clean up the connection to the client
        #but leave the server socket for recieving requests open
        client_sock.shutdown(1)
        client_sock.close()

    # processes a request
    def process_request(self, request):
        print('######\nREQUEST:\n{}######'.format(request))
        linelist = request.strip().split(CRLF)
        reqline = linelist[0]
        postline = linelist[-1]

        for i in range(len(linelist)):
            if linelist[i].startswith( 'Accept:'):
                acceptline = linelist[i]

        rlwords = reqline.split()

        if len(rlwords) == 0:
            return ''

        if rlwords[0] == 'HEAD':
            resource = rlwords[1][1:] # ignore the /

            check = check_accept(acceptline, resource)

            # The format of the requested file does not match the requested acceptable formats
            if check != 'ok':
                return NOT_ACCEPTABLE

            return self.head_command(resource)
        elif rlwords[0] == 'GET':
            resource = rlwords[1][1:] # ignore the /

            check = check_accept(acceptline, resource)

            # The format of the requested file does not match the requested acceptable formats
            if check != 'ok':
                return NOT_ACCEPTABLE

            return self.get_command(resource)
        elif rlwords[0] == 'POST':
            return self.post_command(str(postline))
        else:
            return METHOD_NOT_ALLOWED #+ "405 Error: This method is currently not allowed by this server."

    def head_command(self, resource):
        """Handles HEAD requests."""
        path = os.path.join('.', resource) #look in directory where server is running

        if resource == 'umntc':
          ret = MOVED_PERMANENTLY
        elif not os.path.exists(resource):
          ret = NOT_FOUND
          info = get_contents('404.html')
          return ret + info
        elif not check_perms(resource):
          ret = FORBIDDEN
          info = get_contents('403.html')
          return ret + info
        else:
          ret = OK + '<html><body></body></html>'

        return ret

    #to do a get request, read resource contents and append to ret value.
    #(you should check types of accept lines before doing so)
    def get_command(self, resource):
        """Handles GET requests."""
        path = os.path.join('.', resource) #look in directory where server is running

        if resource == 'umntc':
            ret = MOVED_PERMANENTLY
        elif not os.path.exists(resource):
            ret = NOT_FOUND
            info = get_contents('404.html')
            return bytes(ret, 'utf-8') + info
        elif not check_perms(resource):
            ret = FORBIDDEN
            info = get_contents('403.html')
            return bytes(ret, 'utf-8') + info
        else:
            ret = OK
            info = get_contents(resource) #read the resource
            ret += "Content-Type: " + get_type(resource) + CRLF
            ret += "Content-Length: " + str(len(info)) + CRLF
            ret += CRLF

            return bytes(ret, 'utf-8') + info

        return ret

    def post_command(self, forminfo):
        """Handles POST requests."""
        ret = OK
        ret += "Content-Type: text/html" + CRLF
        ret += CRLF
        forminput = "<html><body><h1>Following Form Data Submitted Successfully:</h1><table><tr>"

        split = forminfo.replace('&', ' ').replace('=', ' ').replace('%3A', ':').split()
        split = split[:10]

        for i in range(len(split)):
            forminput += '<td>' + str(split[i]) + '</td>'

            if i % 2 == 1:
                forminput += '</tr><tr>'

        forminput += '</tr></table></body></html>'

        return ret + forminput

if __name__ == '__main__':
  host, port = 'localhost', 9001

  if len(sys.argv) > 1:
      port = int(sys.argv[1])

  Server(host, port)
