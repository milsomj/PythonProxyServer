import SocketServer
import SimpleHTTPServer
import urllib
import socket
import select
import urlparse
import httplib
import hashlib
import os
import urllib2
import threading
import sys

PORT = 1234
blacklist = []

#This function checks if the requested URL is blocked
def isBlocked(url):
	for x in blacklist:
		if(x in url):
			return True
	return False

#This function is designed to be started as a thread, it listens to the console
#for commands from the user, including block and unblock
def consoleIn():
	while True:
		strIn = raw_input()
		if(strIn == "help"):
			print "Commands:   display-blacklist   block   unblock"
		elif(strIn == "display-blacklist"):
			print blacklist
		else:
			if(strIn.split()[0] == "block" ):
				print "Blocking: ", strIn.split()[1]
				blacklist.append(strIn.split()[1])
			elif(strIn.split()[0] == "unblock"):
				print "Unblocking: ", strIn.split()[1]
				blacklist.remove(strIn.split()[1])
			else:
				print "Command invalid"

#This class handles the proxy requests
class Proxy(SimpleHTTPServer.SimpleHTTPRequestHandler):
	#this function handles CONNECT (HTTPS) requests
	def do_CONNECT(self):
		if(not isBlocked(self.path)):
			print "Path:  " , self.path
			parsedPath = self
			parsedPath.path = "https://%s/" % self.path.replace(':443', '')
			#First we send back a connection established response
			self.send_response(200, "Connection established")
			self.send_header('Connection', 'close')
			self.end_headers()

			u = urlparse.urlsplit(parsedPath.path)
			print "URLSPLIT:  ", u.hostname, "   " , u.port
			address = (u.hostname, u.port or 443)
			#we create a socket to connect to the requested server
			try:
				conn = socket.create_connection(address)
			except socket.error:
				self.send_error(504)    # 504 Gateway Timeout
				return
			#We create an array with the client and server, this allows us to easily handle data from both the client and the server
			conns = [self.connection, conn]
			keep_connection = True
			while keep_connection:
				keep_connection = False
				#while there is data being reveived, the proxy will continue sending data back and forth between the client and server
				rlist, wlist, xlist = select.select(conns, [], conns, self.timeout)
				if xlist:
					break
				for r in rlist:
					other = conns[1] if r is conns[0] else conns[0]
					data = r.recv(8192)
					if data:
						other.sendall(data)
						keep_connection = True
			conn.close()
		else:
			#else -> BLOCKED, send 403 error
			self.send_error(403)
			self.end_headers()
			print "request blocked"

	def do_GET(self):
		print "----------------------------------------------------"
		print "Path:  ", self.path
		if(not isBlocked(self.path)):
			print "request accepted"
			#print out http headers, not implemented
			u = urlparse.urlsplit(self.path)
			x = httplib.HTTPConnection(u.hostname)
			x.request("HEAD", "/index.html")
			#print "Headers:  " , x.getresponse().getheaders()

			#Use hash function to create a file name by passing in the request path
			m = hashlib.md5()
			m.update(self.path)
			cache_filename = m.hexdigest() + ".cached"
			cacheStore = os.path.join("/home/john/Python/proxyCache/",cache_filename)
			#Check cache, let 'data' equal either file from cachestore, or request from server.
			#write 'data' back to client, send 200 response
			if os.path.exists(cacheStore):
				print "Cache hit"
				data = open(cacheStore).readlines()
			else:
				print "Cache miss"
				data = urllib2.urlopen(self.path).readlines()
				open(cacheStore, 'wb').writelines(data)
			self.send_response(200)
			self.end_headers()
			self.wfile.writelines(data)
		else:
			#else -> BLOCKED, send 403 error
			self.send_error(403)
			self.end_headers()
			print "request blocked"

		print "----------------------------------------------------------------"

#start console manager thread
inputThread = threading.Thread(target=consoleIn)
inputThread.start()
#start server
httpd = SocketServer.ForkingTCPServer(('', PORT), Proxy)
print "serving at port", PORT
httpd.serve_forever()
