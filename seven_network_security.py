"""
seven_network_security.py - SOC Analyst Edition with Full Packet Capture
Enterprise-grade network monitoring using tshark/Wireshark
"""

import subprocess
import threading
import time
import re
import socket
import json
import os
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import platform
from pathlib import Path

# ============================================================================
# Data Models
# ============================================================================

class RiskLevel(Enum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class EventType(Enum):
    CONNECTION = "connection"
    PORT_SCAN = "port_scan"
    SUSPICIOUS_TRAFFIC = "suspicious_traffic"
    MALICIOUS_IP = "malicious_ip"
    ANOMALY = "anomaly"
    SYSTEM = "system"
    HOST_DISCOVERED = "host_discovered"

@dataclass
class SecurityEvent:
    timestamp: datetime
    event_type: EventType
    risk_level: RiskLevel
    source_ip: str
    dest_ip: str
    port: int
    protocol: str
    message: str
    details: Dict = field(default_factory=dict)
    mitigated: bool = False

# ============================================================================
# Threat Intelligence
# ============================================================================

class ThreatIntelligence:
    SUSPICIOUS_PORTS = {
        21: {"name": "FTP", "risk": "HIGH", "message": "Clear text FTP - credentials exposed"},
        22: {"name": "SSH", "risk": "MEDIUM", "message": "SSH connection detected"},
        23: {"name": "Telnet", "risk": "CRITICAL", "message": "INSECURE Telnet detected"},
        445: {"name": "SMB", "risk": "CRITICAL", "message": "SMB - ransomware vector"},
        3389: {"name": "RDP", "risk": "HIGH", "message": "RDP connection detected"},
        5900: {"name": "VNC", "risk": "HIGH", "message": "VNC remote access"},
    }
    
    @classmethod
    def get_port_info(cls, port: int) -> Optional[Dict]:
        return cls.SUSPICIOUS_PORTS.get(port)

# ============================================================================
# Network Scanner - Uses ARP and ping to discover hosts
# ============================================================================

class NetworkScanner:
    """Advanced network scanner using ARP and ICMP"""
    
    def __init__(self, interface: str = None):
        self.interface = interface
        self.system = platform.system()
        self.discovered_hosts = []
        
    def get_network_info(self) -> Dict:
        """Get local network information"""
        try:
            # Get default gateway and subnet
            if self.system == "Windows":
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                ip_match = re.search(r'IPv4 Address[.\s]+: (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if ip_match:
                    local_ip = ip_match.group(1)
                    subnet = '.'.join(local_ip.split('.')[:3]) + '.0/24'
                    return {"local_ip": local_ip, "subnet": subnet, "gateway": None}
            else:
                # Linux/WSL - get IP and subnet
                result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
                gateway_match = re.search(r'via (\d+\.\d+\.\d+\.\d+)', result.stdout)
                gateway = gateway_match.group(1) if gateway_match else None
                
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                local_ip = result.stdout.strip().split()[0] if result.stdout else "192.168.1.1"
                subnet = '.'.join(local_ip.split('.')[:3]) + '.0/24'
                
                return {"local_ip": local_ip, "subnet": subnet, "gateway": gateway}
        except Exception as e:
            return {"local_ip": "192.168.1.1", "subnet": "192.168.1.0/24", "gateway": None}
    
    def arp_scan(self) -> List[Dict]:
        """Perform ARP scan to discover hosts (most reliable)"""
        hosts = []
        
        try:
            if self.system == "Windows":
                # Windows: use arp -a
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\w+)', line.lower())
                    if match and match.group(3) != 'invalid':
                        hosts.append({
                            'ip': match.group(1),
                            'mac': match.group(2),
                            'status': 'active'
                        })
            else:
                # Linux/WSL: use arp -n or ip neigh
                result = subprocess.run(['ip', 'neigh', 'show'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    parts = line.split()
                    if len(parts) >= 3 and parts[1] == 'lladdr':
                        hosts.append({
                            'ip': parts[0],
                            'mac': parts[2],
                            'status': parts[3] if len(parts) > 3 else 'reachable'
                        })
        except Exception as e:
            print(f"ARP scan error: {e}")
        
        return hosts
    
    def ping_scan(self, subnet: str = None) -> List[str]:
        """Ping sweep to find active hosts"""
        active_hosts = []
        
        if not subnet:
            net_info = self.get_network_info()
            subnet = net_info['subnet']
        
        # Extract base IP
        base = subnet.split('/')[0]
        base_parts = base.split('.')
        network = '.'.join(base_parts[:3])
        
        print(f"[*] Scanning {network}.1-254 for active hosts...")
        
        def ping_host(ip):
            try:
                if self.system == "Windows":
                    result = subprocess.run(['ping', '-n', '1', '-w', '1000', ip], 
                                           capture_output=True, timeout=2)
                else:
                    result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                                           capture_output=True, timeout=2)
                return ip if result.returncode == 0 else None
            except:
                return None
        
        # Ping all hosts in parallel using threads
        threads = []
        results = []
        
        for i in range(1, 255):
            ip = f"{network}.{i}"
            thread = threading.Thread(target=lambda: results.append(ping_host(ip)))
            thread.start()
            threads.append(thread)
        
        # Wait for all threads with timeout
        for thread in threads:
            thread.join(timeout=5)
        
        active_hosts = [r for r in results if r]
        
        return active_hosts
    
    def full_scan(self, callback: Callable = None) -> Dict:
        """Complete network scan using multiple methods"""
        net_info = self.get_network_info()
        
        if callback:
            callback(f"Starting network scan on {net_info['subnet']}...")
        
        # Method 1: ARP scan (fast, reliable)
        arp_hosts = self.arp_scan()
        
        # Method 2: Ping scan (comprehensive)
        ping_hosts = self.ping_scan()
        
        # Combine results
        all_ips = set()
        for host in arp_hosts:
            all_ips.add(host['ip'])
        for ip in ping_hosts:
            all_ips.add(ip)
        
        # Get hostnames for discovered IPs
        hosts = []
        for ip in all_ips:
            try:
                hostname = socket.gethostbyaddr(ip)[0] if ip != net_info['local_ip'] else "localhost"
            except:
                hostname = "unknown"
            
            hosts.append({
                'ip': ip,
                'hostname': hostname,
                'is_local': ip == net_info['local_ip'],
                'is_gateway': ip == net_info.get('gateway')
            })
        
        self.discovered_hosts = hosts
        
        return {
            'success': True,
            'network': net_info['subnet'],
            'local_ip': net_info['local_ip'],
            'gateway': net_info.get('gateway'),
            'total_hosts': len(hosts),
            'hosts': hosts
        }

# ============================================================================
# Packet Capture Manager - Uses tshark for real capture
# ============================================================================

class PacketCaptureManager:
    """Real-time packet capture using tshark"""
    
    def __init__(self, alert_callback: Callable):
        self.alert_callback = alert_callback
        self.capture_process = None
        self.capturing = False
        self.capture_file = None
        self.packet_count = 0
        self.interface = None
        self.tshark_path = self._find_tshark()
        self.analysis_thread = None
        
    def _find_tshark(self) -> Optional[str]:
        """Find tshark executable"""
        possible_paths = [
            "tshark",
            "/usr/bin/tshark",
            "/mnt/c/Program Files/Wireshark/tshark.exe",
            "C:\\Program Files\\Wireshark\\tshark.exe",
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '--version'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    print(f"[✓] Found tshark at: {path}")
                    return path
            except:
                continue
        return None
    
    def get_interfaces(self) -> List[str]:
        """Get available network interfaces"""
        if not self.tshark_path:
            return []
        
        try:
            result = subprocess.run([self.tshark_path, '-D'], capture_output=True, text=True)
            interfaces = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    # Extract interface name (e.g., "1. eth0")
                    parts = line.split('.', 1)
                    if len(parts) == 2:
                        iface = parts[1].strip().split()[0]
                        interfaces.append(iface)
            return interfaces
        except:
            return []
    
    def start_capture(self, interface: str = None, duration: int = 30, 
                     capture_filter: str = None) -> Dict:
        """Start packet capture with tshark"""
        if not self.tshark_path:
            return {"success": False, "message": "Wireshark/tshark not installed. Install with: sudo apt install wireshark-tshark"}
        
        if self.capturing:
            return {"success": False, "message": "Already capturing"}
        
        # Auto-detect interface if not specified
        if not interface:
            interfaces = self.get_interfaces()
            if interfaces:
                interface = interfaces[0]
            else:
                interface = "eth0"  # Default fallback
        
        self.interface = interface
        
        # Create capture file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.capture_file = f"capture_{timestamp}.pcap"
        
        # Build tshark command
        cmd = [self.tshark_path, '-i', interface, '-w', self.capture_file]
        
        if capture_filter:
            cmd.extend(['-f', capture_filter])
        
        # Also capture with text output for real-time analysis
        analysis_cmd = [self.tshark_path, '-i', interface, '-T', 'fields',
                       '-e', 'ip.src', '-e', 'ip.dst', '-e', 'tcp.port', 
                       '-e', 'udp.port', '-e', 'frame.protocols']
        
        if capture_filter:
            analysis_cmd.extend(['-f', capture_filter])
        
        try:
            # Start the capture process
            self.capture_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.capturing = True
            
            # Start analysis process
            self.analysis_process = subprocess.Popen(analysis_cmd, 
                                                     stdout=subprocess.PIPE, 
                                                     stderr=subprocess.PIPE,
                                                     text=True)
            
            # Start analysis thread
            self.analysis_thread = threading.Thread(target=self._analyze_packets, daemon=True)
            self.analysis_thread.start()
            
            # Stop after duration if specified
            if duration > 0:
                threading.Timer(duration, self.stop_capture).start()
            
            return {
                "success": True, 
                "message": f"Capturing packets on {interface} for {duration} seconds",
                "interface": interface,
                "file": self.capture_file
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _analyze_packets(self):
        """Analyze packets in real-time for threats"""
        while self.capturing and self.analysis_process:
            try:
                line = self.analysis_process.stdout.readline()
                if not line:
                    break
                
                self.packet_count += 1
                
                # Parse packet info
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    src_ip = parts[0] if parts[0] else "unknown"
                    dst_ip = parts[1] if len(parts) > 1 else "unknown"
                    
                    # Check for suspicious ports
                    for part in parts:
                        try:
                            port = int(part)
                            port_info = ThreatIntelligence.get_port_info(port)
                            if port_info:
                                alert_msg = f"Suspicious {port_info['name']} traffic from {src_ip} to {dst_ip}: {port_info['message']}"
                                self.alert_callback(alert_msg, port_info['risk'])
                        except:
                            pass
                    
                    # Check for SSH/Telnet
                    if 'ssh' in str(parts).lower():
                        self.alert_callback(f"SSH traffic detected from {src_ip} to {dst_ip}", "MEDIUM")
                    if 'telnet' in str(parts).lower():
                        self.alert_callback(f"INSECURE Telnet traffic detected from {src_ip} to {dst_ip}", "CRITICAL")
                        
            except Exception as e:
                print(f"Analysis error: {e}")
                break
    
    def stop_capture(self) -> Dict:
        """Stop packet capture"""
        self.capturing = False
        
        if self.capture_process:
            self.capture_process.terminate()
            self.capture_process = None
        
        if self.analysis_process:
            self.analysis_process.terminate()
            self.analysis_process = None
        
        if self.capture_file and os.path.exists(self.capture_file):
            size = os.path.getsize(self.capture_file) / (1024 * 1024)
            return {
                "success": True,
                "message": f"Capture stopped. {self.packet_count} packets captured. File: {self.capture_file} ({size:.2f} MB)",
                "packets": self.packet_count,
                "file": self.capture_file
            }
        
        return {"success": True, "message": "Capture stopped", "packets": self.packet_count}
    
    def analyze_pcap(self, pcap_file: str) -> Dict:
        """Analyze a saved pcap file for threats"""
        if not self.tshark_path:
            return {"success": False, "error": "tshark not found"}
        
        threats = []
        
        try:
            # Get all connections from pcap
            cmd = [self.tshark_path, '-r', pcap_file, '-T', 'fields',
                   '-e', 'ip.src', '-e', 'ip.dst', '-e', 'tcp.port', '-e', 'udp.port']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    for part in parts:
                        try:
                            port = int(part)
                            port_info = ThreatIntelligence.get_port_info(port)
                            if port_info:
                                threats.append({
                                    'port': port,
                                    'service': port_info['name'],
                                    'risk': port_info['risk'],
                                    'message': port_info['message']
                                })
                        except:
                            pass
            
            return {
                "success": True,
                "total_threats": len(threats),
                "threats": threats
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# ============================================================================
# Security Plugin - Main Integration
# ============================================================================

class SecurityPlugin:
    """Main security plugin for Seven"""
    
    def __init__(self, seven_core):
        self.seven = seven_core
        self.scanner = NetworkScanner()
        self.capture = PacketCaptureManager(self._alert)
        self.monitoring = False
        self.monitor_thread = None
        
    def _alert(self, message: str, risk_level: str):
        """Handle security alerts"""
        emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(risk_level, "⚪")
        print(f"\n{emoji} [{risk_level}] {message}")
        
        # Only speak critical/high alerts
        if risk_level in ["CRITICAL", "HIGH"]:
            self.seven.speak(f"Security alert. {risk_level} risk. {message}")
    
    def process_command(self, command: str) -> Tuple[bool, str]:
        """Process security commands"""
        cmd_lower = command.lower().strip()
        
        # Scan network for hosts
        if re.search(r'(?:scan|find).*network.*hosts', cmd_lower) or re.search(r'find.*hosts', cmd_lower):
            self.seven.speak("Scanning network for active hosts. This may take a moment, sir.")
            
            result = self.scanner.full_scan(callback=self.seven.speak)
            
            if result['success']:
                host_list = "\n".join([f"  - {h['ip']} ({h['hostname']})" for h in result['hosts'][:15]])
                if len(result['hosts']) > 15:
                    host_list += f"\n  ... and {len(result['hosts']) - 15} more"
                
                return True, f"Found {result['total_hosts']} active hosts on {result['network']}:\n{host_list}"
            return True, "Network scan failed. Please check your network connection."
        
        # Start packet capture
        if re.search(r'capture\s+packets?', cmd_lower):
            duration = 30
            duration_match = re.search(r'for\s+(\d+)\s+seconds?', cmd_lower)
            if duration_match:
                duration = int(duration_match.group(1))
            
            # Get interface
            interface = None
            iface_match = re.search(r'on\s+(\w+)', cmd_lower)
            if iface_match:
                interface = iface_match.group(1)
            
            result = self.capture.start_capture(interface=interface, duration=duration)
            return True, result["message"]
        
        # Stop capture
        if re.search(r'stop\s+captur', cmd_lower):
            result = self.capture.stop_capture()
            return True, result["message"]
        
        # Show interfaces
        if re.search(r'(?:list|show).*interfaces', cmd_lower):
            interfaces = self.capture.get_interfaces()
            if interfaces:
                iface_list = "\n".join([f"  - {i}" for i in interfaces])
                return True, f"Available network interfaces:\n{iface_list}"
            return True, "No interfaces found or tshark not installed. Install with: sudo apt install wireshark-tshark"
        
        # Analyze pcap file
        if re.search(r'analyze\s+pcap', cmd_lower):
            pcap_match = re.search(r'(\S+\.pcap)', cmd_lower)
            if pcap_match:
                pcap_file = pcap_match.group(1)
                self.seven.speak(f"Analyzing {pcap_file} for threats...")
                result = self.capture.analyze_pcap(pcap_file)
                if result['success']:
                    if result['total_threats'] > 0:
                        threats = "\n".join([f"  - Port {t['port']} ({t['service']}): {t['message']}" for t in result['threats'][:10]])
                        return True, f"Found {result['total_threats']} suspicious connections:\n{threats}"
                    return True, f"No threats found in {pcap_file}"
                return True, f"Analysis failed: {result.get('error', 'Unknown error')}"
        
        # Quick threat check for IP
        if re.search(r'check\s+ip', cmd_lower):
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', cmd_lower)
            if ip_match:
                ip = ip_match.group(1)
                # Quick port scan of common ports
                self.seven.speak(f"Checking {ip} for open ports...")
                common_ports = [22, 23, 80, 443, 445, 3389, 5900]
                open_ports = []
                
                for port in common_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.5)
                        result = sock.connect_ex((ip, port))
                        if result == 0:
                            port_info = ThreatIntelligence.get_port_info(port)
                            open_ports.append(f"{port} ({port_info['name'] if port_info else 'unknown'})")
                        sock.close()
                    except:
                        pass
                
                if open_ports:
                    return True, f"Open ports on {ip}: {', '.join(open_ports)}"
                return True, f"No common open ports found on {ip}"
        
        # Show tshark status
        if re.search(r'tshark\s+status', cmd_lower):
            if self.capture.tshark_path:
                return True, f"tshark is available at: {self.capture.tshark_path}"
            return True, "tshark is not installed. Install with: sudo apt install wireshark-tshark"
        
        return False, ""

# ============================================================================
# Export for integration
# ============================================================================

def integrate_with_seven(seven_core):
    """Integration function for main.py"""
    return SecurityPlugin(seven_core)