import asyncio
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
import logging

# Import existing bridge components
from server.bridge import OMTBridgeServer
from server.handler import PhoneStreamHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class ServerThread(QThread):
    """Thread to run asyncio server"""
    connection_changed = pyqtSignal(int, bool, dict)
    frame_received = pyqtSignal(int, np.ndarray) 
    error_occurred = pyqtSignal(str)
    server_stopped = pyqtSignal()
    
    def __init__(self, bind_ip, start_port, output_type='omt', lib_path='libomt.dll'):
        super().__init__()
        self.bind_ip = bind_ip
        self.start_port = start_port
        self.output_type = output_type
        self.lib_path = lib_path
        self.server = None
        self.loop = None
        self.running = False
        self.shutdown_in_progress = False
        
    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.server = OMTBridgeServer(self.output_type, self.lib_path, self.bind_ip)

            # Set up disconnect signal callback BEFORE patching handlers
            def disconnect_signal_wrapper(phone_id, connected, info):
                """Wrapper to emit disconnect signals safely"""
                if self.running:  # Only emit if thread is still running
                    try:
                        self.connection_changed.emit(phone_id, connected, info)
                    except RuntimeError:
                        logger.debug(f"Could not emit signal for phone {phone_id} (Qt cleaned up)")
            
            self.server._disconnect_signal_callback = disconnect_signal_wrapper
            
            for i, config in enumerate(self.server.configs):
                config.port = self.start_port + i
            
            self._patch_handlers()
            
            self.running = True
            logger.info(f"Server starting on {self.bind_ip}:{self.start_port}")
            
            self.loop.run_until_complete(self._run_server())
            
        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            if not self.shutdown_in_progress:  # Only emit if not shutting down
                self.error_occurred.emit(str(e))
        finally:
            self.running = False
            self.cleanup_loop()
            self.server_stopped.emit()
    
    async def _run_server(self):
        try:
            await self.server.start() # type: ignore
        except asyncio.CancelledError:
            logger.info("Server start cancelled, cleaning up...")
            raise
    
    def _patch_handlers(self):
        """Patch handlers to emit Qt signals with robust error handling"""
        original_handle = PhoneStreamHandler.handle_client
        thread = self
        
        async def patched_handle(handler, reader, writer):
            try:
                # Initial connection signal
                try:
                    thread.connection_changed.emit(handler.config.phone_id, True, {})
                except Exception as e:
                    logger.error(f"Error emitting initial connection signal: {e}")
                
                # Patch config receiver
                orig_config = handler.receive_config
                async def patched_config(r):
                    result = await orig_config(r)
                    if result:
                        try:
                            info = {
                                'device_model': handler.device_model,
                                'battery': handler.battery_percent,
                                'temperature': handler.cpu_temperature_celsius,
                                'resolution': f"{handler.current_width}x{handler.current_height}",
                                'fps': handler.current_fps,
                                'latency': handler.average_latency,
                                'handler': handler
                            }
                            thread.connection_changed.emit(handler.config.phone_id, True, info)
                        except Exception as e:
                            logger.error(f"Error emitting config signal: {e}")
                    return result
                
                handler.receive_config = patched_config

                # Patch video processing for frame preview
                orig_process_video = handler.process_video_frame
                async def patched_process_video(data, flags, receive_time):
                    result = await orig_process_video(data, flags, receive_time)
                    
                    # Send RGB frame to GUI - but DON'T re-decode, handler already did it
                    if result and thread.running and not (flags & 0x2):
                        try:
                            # Handler already has the decoded frame in NV12 format
                            # Just convert the last NV12 data to RGB
                            if hasattr(handler, '_last_nv12_frame'):
                                rgb_frame = handler.nv12_to_rgb(
                                    handler._last_nv12_frame,
                                    handler.current_width,
                                    handler.current_height
                                )
                                thread.frame_received.emit(handler.config.phone_id, rgb_frame)
                        except Exception as e:
                            logger.debug(f"GUI frame error: {e}")  # Don't let GUI errors affect streaming
                    
                    return result
                
                handler.process_video_frame = patched_process_video

                # Call original handler
                await original_handle(handler, reader, writer)
                
            except asyncio.CancelledError:
                logger.info(f"Handler for phone {handler.config.phone_id} cancelled")
                raise
            except Exception as e:
                logger.error(f"Handler error for phone {handler.config.phone_id}: {e}", exc_info=True)
            finally:
                # Emit disconnect signal, checking if we're shutting down
                try:
                    if thread.running and not thread.shutdown_in_progress:
                        thread.connection_changed.emit(handler.config.phone_id, False, {})
                        logger.debug(f"Emitted disconnect for phone {handler.config.phone_id}")
                    else:
                        logger.debug(f"Skipping disconnect signal for phone {handler.config.phone_id} - shutdown in progress")
                except RuntimeError as e:
                    logger.debug(f"Could not emit disconnect signal: {e}")
                except Exception as e:
                    logger.error(f"Error emitting disconnect signal: {e}", exc_info=True)
        
        PhoneStreamHandler.handle_client = patched_handle # type: ignore

    def cleanup_loop(self):
        """Properly cleanup asyncio loop"""
        if self.loop and not self.loop.is_closed():
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                
                # Give tasks a moment to cancel
                if pending:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                
                self.loop.close()
                logger.debug("Asyncio loop cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up loop: {e}")
    
    def stop(self):
        """Stop server gracefully"""
        if not self.running or self.shutdown_in_progress:
            return
        
        logger.info("Stopping server from GUI...")
        self.shutdown_in_progress = True
        
        if self.loop and self.server:
            try:
                # Schedule stop on the event loop
                future = asyncio.run_coroutine_threadsafe(self._async_stop(), self.loop)
                # Wait for stop to complete (with timeout)
                try:
                    future.result(timeout=5)
                    logger.info("✅ Server stopped successfully")
                except asyncio.TimeoutError:
                    logger.warning("⚠️  Server stop timed out after 5 seconds")
            except Exception as e:
                logger.error(f"Error during stop: {e}", exc_info=True)

        # Set running to False after signals sent
        self.running = False
        
        # Wait for thread to finish
        self.quit()
        if not self.wait(5000):
            logger.warning("Thread terminating")
            self.terminate()
            self.wait(1000)  # Give it a moment after terminate

    async def _async_stop(self):
        try:
            if self.server:
                await self.server.stop()
        except Exception as e:
            logger.error(f"Error stopping: {e}")