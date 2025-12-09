import asyncio
from typing import Any
import netifaces
import logging

from .config import StreamConfig
from .outputs import OMTOutput, NativeWindowsOutput
from .handler import PhoneStreamHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class OMTBridgeServer:
    """Main server managing multiple phone streams"""
    
    def __init__(self, output_type: str = "omt", omt_lib_path: str = "libomt.dll", bind_ip: str | None = None):
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
        self.streams = {}
        self.servers = []
        self.outputs = {}  # Track all outputs for proper cleanup
        self.active_handlers = {} # Track active connection handlers
        self._disconnect_signal_callback: Any | None = None
        
        # Default configuration for 4 phones
        self.configs = [
            StreamConfig(1, 5000, "Camera 1", 1280, 720, 30),
            StreamConfig(2, 5001, "Camera 2", 1280, 720, 30),
            StreamConfig(3, 5002, "Camera 3", 1280, 720, 30),
            StreamConfig(4, 5003, "Camera 4", 1280, 720, 30),
        ]

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
        
        # Create servers for each phone
        for config in self.configs:
            try:
                # Create output based on selected type
                if self.output_type == "native":
                    output = NativeWindowsOutput(config.width, config.height, config.fps, config.phone_id)
                else:  # Default to OMT
                    output = OMTOutput(config.name, self.omt_lib_path)
                
                handler = PhoneStreamHandler(config, output)
                self.streams[config.phone_id] = handler
                self.outputs[config.phone_id] = output  # Track for cleanup

                def make_handler(handler, phone_id):
                    async def client_handler_wrapper(reader, writer):
                        # Register active handler
                        self.active_handlers[phone_id] = handler
                        try:
                            await handler.handle_client(reader, writer)
                        finally:
                            # Unregister when done
                            self.active_handlers.pop(phone_id, None)
                    return client_handler_wrapper
                
                # Bind to specific IP or all interfaces
                server = await asyncio.start_server(
                    make_handler(handler, config.phone_id),
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
            logger.info("   Add OMT inputs to vMix: M-Camera 1, M-Camera 2, M-Camera 3, M-Camera 4")
        
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
    
    async def stop(self):
        """Stop the server gracefully and disconnect all clients"""
        logger.info("\nStopping Bridge Server...")

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