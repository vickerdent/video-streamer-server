"""
Network Diagnostic Tool
Run this before starting the bridge server to diagnose network issues
Usage: python network_diagnostic.py
"""

import socket
import netifaces
import subprocess
import platform
import re

def get_windows_interface_name(guid):
    """Convert Windows GUID to friendly name"""
    if platform.system().lower() != 'windows':
        return guid
    
    try:
        # Remove curly braces if present
        clean_guid = guid.strip('{}')
        
        # Query Windows registry for friendly name
        cmd = f'reg query "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Network\\{{4D36E972-E325-11CE-BFC1-08002BE10318}}\\{{{clean_guid}}}\\Connection" /v Name'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
        
        if result.returncode == 0:
            # Parse the output to get the name
            match = re.search(r'Name\s+REG_SZ\s+(.+)', result.stdout)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    
    # Fallback: try to guess from IP range
    return guess_interface_type(guid)

def guess_interface_type(interface_name):
    """Guess interface type from name patterns"""
    name_lower = interface_name.lower()
    
    if 'eth' in name_lower:
        return 'Ethernet'
    elif 'wi-fi' in name_lower or 'wifi' in name_lower or 'wlan' in name_lower:
        return 'Wi-Fi'
    elif 'vethernet' in name_lower or 'hyper-v' in name_lower:
        return 'Virtual Adapter (Hyper-V)'
    elif 'vmware' in name_lower or 'virtualbox' in name_lower:
        return 'Virtual Adapter (VM)'
    elif 'loopback' in name_lower or 'lo' == name_lower:
        return 'Loopback'
    
    return interface_name

def categorize_network(ip, interface_name):
    """Categorize network type based on IP and interface"""
    # Virtual/WSL networks
    if ip.startswith('172.') and ('hyper-v' in interface_name.lower() or 'vethernet' in interface_name.lower()):
        return '🔷 Virtual (WSL/Hyper-V)'
    
    # Common home router ranges
    if ip.startswith('192.168.0.'):
        return '🏠 Home Network'
    elif ip.startswith('192.168.1.'):
        return '🏠 Home Network'
    elif ip.startswith('10.'):
        return '🏢 Private Network'
    elif ip.startswith('172.'):
        return '🔷 Private/Virtual Network'
    
    return '🌐 Network'

def get_all_interfaces():
    """Get all network interfaces with details"""
    print("\n" + "="*60)
    print("🔍 NETWORK INTERFACES")
    print("="*60)
    
    interfaces = netifaces.interfaces()
    interface_details = []
    
    for interface in interfaces:
        try:
            addrs = netifaces.ifaddresses(interface)
            
            # Get IPv4 info
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get('addr')
                    netmask = addr_info.get('netmask', 'N/A')
                    
                    if ip and ip != '127.0.0.1':
                        # Get friendly name
                        friendly_name = get_windows_interface_name(interface)
                        network_type = categorize_network(ip, friendly_name)
                        
                        interface_details.append({
                            'interface': interface,
                            'friendly_name': friendly_name,
                            'ip': ip,
                            'netmask': netmask,
                            'network_type': network_type
                        })
                        
                        print(f"\n📡 {friendly_name}")
                        print(f"   {network_type}")
                        print(f"   IP Address: {ip}")
                        print(f"   Netmask:    {netmask}")
                        
                        # Try to get MAC address
                        if netifaces.AF_LINK in addrs:
                            mac = addrs[netifaces.AF_LINK][0].get('addr', 'N/A')
                            print(f"   MAC:        {mac}")
        except Exception as e:
            print(f"⚠️  Error reading {interface}: {e}")
    
    return interface_details

def test_port_binding(ip, port=5000):
    """Test if we can bind to a specific IP and port"""
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((ip, port))
        test_socket.close()
        return True
    except Exception:
        return False

def get_default_gateway():
    """Get the default gateway"""
    try:
        gateways = netifaces.gateways()
        default_gateway = gateways.get('default', {}).get(netifaces.AF_INET) # type: ignore
        
        if default_gateway:
            gateway_ip, interface = default_gateway
            friendly_name = get_windows_interface_name(interface)
            return gateway_ip, friendly_name
    except Exception:
        pass
    
    return None, None

def test_connectivity():
    """Test basic connectivity"""
    print("\n" + "="*60)
    print("🌐 CONNECTIVITY TEST")
    print("="*60)
    
    # Get default gateway
    gateway_ip, gateway_interface = get_default_gateway()
    
    if gateway_ip:
        print(f"\n✅ Default Gateway: {gateway_ip} (via {gateway_interface})")
        
        # Ping gateway
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', gateway_ip]
        
        try:
            result = subprocess.run(command, capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✅ Gateway reachable")
            else:
                print("❌ Gateway NOT reachable")
        except Exception as e:
            print(f"⚠️  Could not ping gateway: {e}")
    else:
        print("❌ No default gateway found")

def check_firewall():
    """Check Windows Firewall status"""
    if platform.system().lower() != 'windows':
        return
    
    print("\n" + "="*60)
    print("🔥 FIREWALL CHECK")
    print("="*60)
    
    try:
        # Check if Windows Firewall is blocking ports
        result = subprocess.run(
            ['netsh', 'advfirewall', 'show', 'currentprofile'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if 'State' in result.stdout:
            print("\n⚠️  Windows Firewall is active")
            print("   Make sure Python is allowed through the firewall:")
            print("   1. Open Windows Defender Firewall")
            print("   2. Click 'Allow an app through firewall'")
            print("   3. Add Python and allow Private networks")
        else:
            print("\n✅ Firewall status: OK")
    except Exception as e:
        print(f"\n⚠️  Could not check firewall: {e}")

def recommend_settings(interfaces):
    """Recommend the best settings"""
    print("\n" + "="*60)
    print("💡 RECOMMENDATIONS")
    print("="*60)
    
    if not interfaces:
        print("\n❌ No network interfaces found!")
        return
    
    # Filter out virtual adapters for primary recommendations
    real_interfaces = [iface for iface in interfaces 
                      if not ('Virtual' in iface['network_type'] or 
                             'WSL' in iface['network_type'] or
                             'Hyper-V' in iface['network_type'])]
    
    if real_interfaces:
        print("\n📱 RECOMMENDED FOR PHONE CONNECTION:")
        for idx, iface in enumerate(real_interfaces, 1):
            can_bind = test_port_binding(iface['ip'])
            status = "✅" if can_bind else "❌"
            
            print(f"\n   {status} Option {idx}: {iface['ip']} ({iface['friendly_name']})")
            print(f"      {iface['network_type']}")
            print(f"      Command: python src\\omt_bridge_tcp.py --bind-ip {iface['ip']}")
            
            if not can_bind:
                print("      ⚠️  Cannot bind to this IP (may be in use or restricted)")
    
    # Show virtual adapters separately
    virtual_interfaces = [iface for iface in interfaces 
                         if 'Virtual' in iface['network_type'] or 
                            'WSL' in iface['network_type'] or
                            'Hyper-V' in iface['network_type']]
    
    if virtual_interfaces:
        print("\n\n🔷 VIRTUAL ADAPTERS (not recommended for phone):")
        for iface in virtual_interfaces:
            print(f"   • {iface['ip']} ({iface['friendly_name']})")
    
    print("\n\n⚠️  IMPORTANT:")
    print("   • Connect your phone to the SAME network as the IP you choose")
    print("   • Use the IP from 'Home Network' for best results")
    print("   • Make sure Windows Firewall allows Python")

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         Mobile Camera Bridge - Network Diagnostic        ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Get all network interfaces
    interfaces = get_all_interfaces()
    
    # Test connectivity
    test_connectivity()
    
    # Check firewall (Windows only)
    check_firewall()
    
    # Recommend settings
    recommend_settings(interfaces)
    
    print("\n" + "="*60)
    print("✅ Diagnostic complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")