import asyncio
from typing import Any
import netifaces
import logging

from server.config import StreamConfig

from .outputs import OMTOutput, NativeWindowsOutput
from .handler import PhoneStreamHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class OMTBridgeServer:
    """Main server managing multiple phone streams"""
    
    def __init__(self, output_type: str = "omt", omt_lib_path: str = "libomt.dll", bind_ip: str | None = None, omt_quality: int = 50):
        """
        Initialize bridge server
        
        Args:
            output_type: "omt" for vMix OMT protocol, "virtual" for virtual camera/mic
            omt_lib_path: Path to libomt.dll
            bind_ip: Specific IP to bind to (None = auto-detect)
        """
        self.output_type = output_type.lower()
        self.omt_lib_path = omt_lib_path
        self.bind_ip = bind_ip
        self.omt_quality = omt_quality
        self.streams = {}
        self.servers = []
        self.outputs = {}  # Track all outputs for proper cleanup
        self.active_handlers = {} # Track active connection handlers
        self._disconnect_signal_callback: Any | None = None
        self._network_status_callback: Any | None = None
        self.configs: list[StreamConfig] = [] # Configs will be set by ServerThread before starting

        # Track active connections per port to prevent duplicates
        self.port_connections = {}  # port -> handler mapping
        self.connection_lock = asyncio.Lock()  # Lock for thread-safe access

        # Network monitoring
        self.current_bind_ip = None
        self.network_monitor_task = None

    def get_local_ip_addresses(self):
        """Get all local IP addresses from all network interfaces"""
        ip_addresses = []
        
        try:
            # Get all network interfaces
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                # Get addresses for this interface
                addrs = netifaces.ifaddresses(interface)
                
                # Check for IPv4 addresses
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and ip != '127.0.0.1':  # Skip loopback
                            # Get netmask if available
                            netmask = addr_info.get('netmask', '255.255.255.0')
                            ip_addresses.append({
                                'interface': interface,
                                'ip': ip,
                                'netmask': netmask
                            })
        except Exception as e:
            logger.warning(f"Error getting network interfaces: {e}")
        
        return ip_addresses
    
    def select_best_interface(self, ip_addresses):
        """Select the best IP address to bind to"""
        if not ip_addresses:
            return '0.0.0.0'  # Fallback to all interfaces
        
        # Prioritize non-virtual, non-VPN interfaces
        # Common patterns: "Ethernet", "Wi-Fi", "en0", "wlan0", "eth0"
        priority_patterns = ['ethernet', 'wi-fi', 'wlan', 'eth', 'en']
        
        for pattern in priority_patterns:
            for addr_info in ip_addresses:
                if pattern in addr_info['interface'].lower():
                    logger.info(f"Selected interface: {addr_info['interface']} ({addr_info['ip']})")
                    return addr_info['ip']
        
        # If no priority match, use first non-loopback
        if ip_addresses:
            logger.info(f"Using first available interface: {ip_addresses[0]['interface']} ({ip_addresses[0]['ip']})")
            return ip_addresses[0]['ip']
        
        return '0.0.0.0'
    
    async def start(self):
        """Start the bridge server"""
        logger.info("=" * 60)
        logger.info(f"🚀 Bridge Server Starting ({self.output_type.upper()})...")
        logger.info("=" * 60)

        # Determine which IP to bind to
        if self.bind_ip:
            bind_address = self.bind_ip
            logger.info(f"📡 Using specified bind address: {bind_address}")
        else:
            # Auto-detect network interfaces
            ip_addresses = self.get_local_ip_addresses()
            
            if ip_addresses:
                logger.info("📡 Available network interfaces:")
                for addr_info in ip_addresses:
                    logger.info(f"   - {addr_info['interface']}: {addr_info['ip']}/{addr_info['netmask']}")
                
                # Select best interface
                bind_address = self.select_best_interface(ip_addresses)
            else:
                logger.warning("⚠️ No network interfaces found, binding to all (0.0.0.0)")
                bind_address = '0.0.0.0'

        # Store the bind address for monitoring
        self.current_bind_ip = bind_address
        
        # Create servers for each phone
        for config in self.configs:
            try:
                # Create output based on selected type
                if self.output_type == "native":
                    output = NativeWindowsOutput(config.width, config.height, config.fps, config.phone_id)
                else:  # Default to OMT
                    output = OMTOutput(config.name, self.omt_lib_path, self.omt_quality)
                
                handler = PhoneStreamHandler(config, output)
                self.streams[config.phone_id] = handler
                self.outputs[config.phone_id] = output  # Track for cleanup

                def make_handler(handler, phone_id, port_number):
                    async def client_handler_wrapper(reader, writer):
                        addr = writer.get_extra_info('peername')

                        # Check if this port already has an active connection
                        async with self.connection_lock:
                            if port_number in self.port_connections:
                                existing_handler = self.port_connections[port_number]
                                if existing_handler and existing_handler.running:
                                    logger.error(
                                        f"❌ REJECTED: Phone trying to connect to port {port_number} "
                                        f"which already has an active connection from {existing_handler.writer.get_extra_info('peername') if existing_handler.writer else 'unknown'}"
                                    )
                                    logger.error(f"   New connection from {addr[0]}:{addr[1]} was DENIED")
                                    
                                    # Send rejection message and close
                                    try:
                                        writer.write(b"ERROR: Port already in use\n")
                                        await writer.drain()
                                        writer.close()
                                        await writer.wait_closed()
                                    except Exception as e:
                                        logger.error(f"Error sending rejection: {e}")
                                    
                                    return
                            
                            # Register this connection
                            self.port_connections[port_number] = handler
                            logger.info(f"✅ Port {port_number} assigned to connection from {addr[0]}:{addr[1]}")
                        
                        # Register active handler
                        self.active_handlers[phone_id] = handler
                        try:
                            await handler.handle_client(reader, writer)
                        finally:
                            # Unregister when done
                            self.active_handlers.pop(phone_id, None)

                            # Clear port assignment
                            async with self.connection_lock:
                                if self.port_connections.get(port_number) == handler:
                                    self.port_connections.pop(port_number, None)
                                    logger.info(f"🔓 Port {port_number} released")

                    return client_handler_wrapper
                
                # Bind to specific IP or all interfaces
                server = await asyncio.start_server(
                    make_handler(handler, config.phone_id, config.port),
                    bind_address,  # Use selected IP instead of '0.0.0.0'
                    config.port,
                    reuse_address=True  # Allow quick restart
                )
                self.servers.append(server)
                
                # Get actual listening address
                addr = server.sockets[0].getsockname()
                logger.info(f"📱 Phone {config.phone_id} → {addr[0]}:{addr[1]}")
            except Exception as e:
                logger.error(f"❌ Failed to create output for Phone {config.phone_id}: {e}")

        # Start network monitoring AFTER servers are created
        self.network_monitor_task = asyncio.create_task(self.monitor_network())
        
        logger.info("=" * 60)
        if self.output_type == "native":
            logger.info("✅ Bridge ready! Native Windows camera integration:")
            logger.info("   📹 Video: Connect VirtualCameraWrapper.exe on port 9999")
            logger.info("   🎤 Audio: Not yet implemented (Phase 2)")
            logger.info("")
            logger.info("   Usage: Start wrapper, then this bridge will send frames")
            logger.info("   Once running, cameras appear in Zoom, Teams, Meet, Discord, OBS, etc.")
        else:
            logger.info("✅ Bridge ready! Streaming to vMix via OMT protocol")
            logger.info("   Add OMT inputs to vMix: Camera 1, Camera 2, Camera 3, Camera 4")
        
        logger.info("")
        logger.info("📱 Connect your phone to these addresses:")
        if bind_address == '0.0.0.0':
            # Show all available IPs
            ip_addresses = self.get_local_ip_addresses()
            for addr_info in ip_addresses:
                logger.info(f"   - {addr_info['ip']} ({addr_info['interface']})")
        else:
            logger.info(f"   - {bind_address}")
        
        logger.info("=" * 60)
        
        try:
            await asyncio.gather(*[server.serve_forever() for server in self.servers])
        except KeyboardInterrupt:
            logger.info("\n👋 Shutting down...")
        finally:
            await self.stop()

    def update_omt_quality(self, quality_value: int):
        """Update OMT quality for all outputs"""
        logger.info(f"Updating OMT quality to {quality_value}")
        for phone_id, output in self.outputs.items():
            if isinstance(output, OMTOutput):
                try:
                    output.update_quality(quality_value)
                except Exception as e:
                    logger.error(f"Failed to update quality for phone {phone_id}: {e}")

    async def monitor_network(self):
        """Monitor network availability"""
        last_status = True  # Assume network is up initially
        consecutive_failures = 0
        max_failures = 2  # Require 2 consecutive failures before declaring network down

        logger.info(f"🔍 Network monitoring started for {self.current_bind_ip}")

        while True:
            try:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                # Check if our bind IP is still available
                if self.current_bind_ip and self.current_bind_ip != '0.0.0.0':
                    current_ips = self.get_local_ip_addresses()
                    ip_still_exists = any(
                        addr['ip'] == self.current_bind_ip 
                        for addr in current_ips
                    )

                    # Count consecutive failures to avoid false positives
                    if not ip_still_exists:
                        consecutive_failures += 1
                        logger.debug(f"Network check failed ({consecutive_failures}/{max_failures})")
                    else:
                        consecutive_failures = 0
                    
                    # Network went down
                    if not ip_still_exists and consecutive_failures >= max_failures and last_status:
                        logger.error(f"❌ Network interface {self.current_bind_ip} is no longer available!")
                        logger.error("   The server is not reachable until network is restored.")
                        
                        last_status = False
                        
                        # Notify GUI IMMEDIATELY
                        if self._network_status_callback:
                            try:
                                logger.info("📡 Notifying GUI: Network DOWN")
                                self._network_status_callback(False, self.current_bind_ip)
                            except Exception as e:
                                logger.error(f"Error in network status callback: {e}")
                        
                        # Disconnect all clients
                        if self.active_handlers:
                            logger.info(f"📴 Disconnecting {len(self.active_handlers)} client(s) due to network loss...")
                            disconnect_tasks = []
                            for phone_id, handler in list(self.active_handlers.items()):
                                disconnect_tasks.append(handler.force_disconnect())
                            
                            if disconnect_tasks:
                                await asyncio.gather(*disconnect_tasks, return_exceptions=True)
                            
                            logger.info("✅ All clients disconnected")
                    
                    # Network came back up
                    elif ip_still_exists and not last_status:
                        logger.info(f"✅ Network {self.current_bind_ip} restored!")
                        last_status = True
                        consecutive_failures = 0
                        
                        # Notify GUI of restoration
                        if self._network_status_callback:
                            try:
                                logger.info("📡 Notifying GUI: Network UP")
                                self._network_status_callback(True, self.current_bind_ip)
                            except Exception as e:
                                logger.error(f"Error in network status callback: {e}")
                        
            except asyncio.CancelledError:
                logger.debug("Network monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Network monitoring error: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Stop the server gracefully and disconnect all clients"""
        logger.info("\nStopping Bridge Server...")

        # Cancel network monitoring
        if self.network_monitor_task:
            self.network_monitor_task.cancel()
            try:
                await self.network_monitor_task
            except asyncio.CancelledError:
                pass

        # Emit disconnect signals for GUI BEFORE closing connections
        if self._disconnect_signal_callback:
            logger.info("📡 Notifying GUI of disconnections...")
            for phone_id in list(self.active_handlers.keys()):
                try:
                    self._disconnect_signal_callback(phone_id, False, {})
                    logger.debug(f"  Sent disconnect signal for phone {phone_id}")
                except Exception as e:
                    logger.error(f"  Error sending disconnect signal for phone {phone_id}: {e}")

        # Force disconnect all active phone connections
        if self.active_handlers:
            logger.info(f"📴 Disconnecting {len(self.active_handlers)} active phone(s)...")
            
            # Create tasks to disconnect all handlers concurrently
            disconnect_tasks = []
            for phone_id, handler in list(self.active_handlers.items()):
                logger.debug(f"  Disconnecting phone {phone_id}...")
                disconnect_tasks.append(handler.force_disconnect())
            
            if disconnect_tasks:
                # Wait for all disconnections (with timeout)
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*disconnect_tasks, return_exceptions=True),
                        timeout=3.0
                    )
                    logger.info("✅ All phones disconnected")
                except asyncio.TimeoutError:
                    logger.warning("⚠️  Phone disconnection timeout (some may still be active)")
        
        # Close all server sockets
        logger.info("🔒 Closing server sockets...")
        for i, server in enumerate(self.servers):
            try:
                server.close()
                await asyncio.wait_for(server.wait_closed(), timeout=2.0)
                logger.debug(f"  Server {i+1} closed")
            except asyncio.TimeoutError:
                logger.warning(f"  Server {i+1} close timeout")
            except Exception as e:
                logger.error(f"  Error closing server {i+1}: {e}")

        # Clear the servers list
        self.servers.clear()
        
        # Give OS time to release ports
        logger.info("⏳ Waiting for port release...")
        await asyncio.sleep(1.0)
        
        # Give handlers time to finish cleaning up
        logger.debug("⏳ Waiting for handlers to finish...")
        await asyncio.sleep(0.5)
        
        # Stop all streams (mark as not running)
        for phone_id in list(self.streams.keys()):
            handler = self.streams[phone_id]
            handler.running = False  # Signal handler to stop
        
        # Destroy all outputs (DirectShow or OMT)
        for phone_id, output in self.outputs.items():
            try:
                output.destroy()
            except Exception as e:
                logger.error(f"Error destroying output for Phone {phone_id}: {e}")
        
        logger.info("✅ Server stopped successfully")