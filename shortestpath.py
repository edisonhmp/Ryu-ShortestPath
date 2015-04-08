
"""
An OpenFlow 1.0 shortest path forwarding implementation.
"""
import logging
import struct
from ryu.base import app_manager
from ryu.controller import mac_to_port
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology.api import get_switch, get_link
from ryu.app.wsgi import ControllerBase
from ryu.topology import event, switches
import networkx as nx
class ProjectController(app_manager.RyuApp):
        OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]
        def __init__(self, *args, **kwargs):
                super(ProjectController, self).__init__(*args, **kwargs)
                self.mac_to_port = {}
                self.topology_api_app = self
                self.net=nx.DiGraph()
                self.nodes = {}
                self.links = {}
                self.no_of_nodes = 0
                self.no_of_links = 0
                self.i=0
        
        def ls(self,obj):
                print("\n".join([x for x in dir(obj) if x[0] != "_"]))

        def add_flow(self, datapath, in_port, dst, actions):
        	ofproto = datapath.ofproto
		match = datapath.ofproto_parser.OFPMatch(
		in_port=in_port, dl_dst=haddr_to_bin(dst))
		mod = datapath.ofproto_parser.OFPFlowMod(
		datapath=datapath, match=match, cookie=0,
		command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
		priority=ofproto.OFP_DEFAULT_PRIORITY,
		flags=ofproto.OFPFF_SEND_FLOW_REM, actions=actions)
		datapath.send_msg(mod)

	@set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
	def _packet_in_handler(self, ev):
		msg = ev.msg
		datapath = msg.datapath
		ofproto = datapath.ofproto
		pkt = packet.Packet(msg.data)
		eth = pkt.get_protocol(ethernet.ethernet)
		dst = eth.dst
		src = eth.src
		dpid = datapath.id
		self.mac_to_port.setdefault(dpid, {})

		if src not in self.net:
			self.net.add_node(src)
			self.net.add_edge(dpid,src,{'port':msg.in_port})
			self.net.add_edge(src,dpid)
		if dst in self.net:
			path=nx.shortest_path(self.net,src,dst)
			next=path[path.index(dpid)+1]
			out_port=self.net[dpid][next]['port']
		else:
			out_port = ofproto.OFPP_FLOOD
			actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
		# install a flow to avoid packet_in next time
		if out_port != ofproto.OFPP_FLOOD:
			self.add_flow(datapath, msg.in_port, dst, actions)
			out = datapath.ofproto_parser.OFPPacketOut(
			datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
			actions=actions)
			datapath.send_msg(out)
	@set_ev_cls(event.EventSwitchEnter)
	def get_topology_data(self, ev):
		switch_list = get_switch(self.topology_api_app, None)
		switches=[switch.dp.id for switch in switch_list]
		self.net.add_nodes_from(switches)		
		links_list = get_link(self.topology_api_app, None)
		#print links_list
		links=[(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in 			links_list]
		#print links
		self.net.add_edges_from(links)
		links=[(link.dst.dpid,link.src.dpid,{'port':link.dst.port_no}) for link in 			links_list]
		#print links
		self.net.add_edges_from(links)
		print "**********List of links"
		print self.net.edges()

