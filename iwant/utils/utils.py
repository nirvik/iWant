import string
import random
import socket
from netifaces import interfaces, ifaddresses, AF_INET

def generate_secret(size=10, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

def generate_size():
	return random.randint(6,10)

def get_ips():
	ip = socket.gethostbyhostname(socket.gethostname())
	return ip

class EventHooker(object):
	__doc__ = """
		Registering custom event callbacks
	"""
	def __init__(self):
		self.events = {}

	def bind(self,event,callback):
		'''
		 Registers callbacks to an event
		:param event : string
		:param callback : function
		'''
		self.events[event] = callback

	def unbind(self,event):
		'''
		Detach events from the hooker
		:param event: string
		'''
		if event in self.events:
			del self.events[event]
