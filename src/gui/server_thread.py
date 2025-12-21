import asyncio
import logging
from concurrent import futures

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

# Import existing bridge components
from server.bridge import OMTBridgeServer
from server.handler import PhoneStreamHandler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class ServerThread(QThread):
    """Thread to run asyncio server"""

    connection_changed = pyqtSignal(int, bool, dict)
    frame_received = pyqtSignal(int, np.ndarray)
    error_occurred = pyqtSignal(str)
    server_stopped = pyqtSignal()
    network_status_changed = pyqtSignal(bool, str)

    def __init__(
        self,
        bind_ip,
        start_port,
        output_type="omt",
        lib_path="libomt.dll",
        camera_count=4,
        omt_quality="medium",
    ):
        super().__init__()
        self.bind_ip = bind_ip
        self.start_port = start_port
        self.output_type = output_type
        self.lib_path = lib_path
        self.camera_count = camera_count
        self.omt_quality = omt_quality
        self.server: OMTBridgeServer | None = None
        self.loop = None
        self.running = False
        self.shutdown_in_progress = False

    def run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # Map quality string to int
            quality_map = {"low": 1, "medium": 50, "high": 100}
            quality_value = quality_map.get(self.omt_quality, 50)

            logger.info(
                f"Starting server with OMT quality: {self.omt_quality} ({quality_value})"
            )

            self.server = OMTBridgeServer(
                self.output_type, self.lib_path, self.bind_ip, quality_value
            )

            # Set up callbacks patching handlers
            def disconnect_signal_wrapper(phone_id, connected, info):
                """Wrapper to emit disconnect signals safely"""
                if self.running:  # Only emit if thread is still running
                    try:
                        self.connection_changed.emit(phone_id, connected, info)
                    except RuntimeError:
                        logger.debug(
                            f"Could not emit signal for phone {phone_id} (Qt cleaned up)"
                        )

            def network_status_wrapper(available, ip):
                logger.info(
                    f"🔔 Network status callback triggered: available={available}, ip={ip}"
                )
                if self.running:
                    try:
                        self.network_status_changed.emit(available, ip)
                        logger.debug(f"✅ Network status signal emitted: {available}")
                    except RuntimeError as e:
                        logger.debug(f"Could not emit network status signal: {e}")
                    except Exception as e:
                        logger.error(f"Error emitting network status: {e}")
                else:
                    logger.debug("Server not running, skipping network status signal")

            self.server._disconnect_signal_callback = disconnect_signal_wrapper
            self.server._network_status_callback = network_status_wrapper

            logger.info("✅ Network status callback registered")

            # Configure ports dynamically based on camera_count
            self.server.configs = []
            for i in range(self.camera_count):
                from server.config import StreamConfig

                config = StreamConfig(
                    i + 1, self.start_port + i, f"VSS Camera {i + 1}", 1280, 720, 30
                )
                self.server.configs.append(config)

            self._patch_handlers()

            self.running = True
            logger.info(
                f"Server starting with {self.camera_count} cameras on {self.bind_ip}:{self.start_port}"
            )

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
            await self.server.start() if self.server else None
        except asyncio.CancelledError:
            logger.info("Server start cancelled, cleaning up...")
            raise

    def _patch_handlers(self):
        """Patch handlers to emit Qt signals with robust error handling"""
        original_handle = PhoneStreamHandler.handle_client
        thread = self

        async def patched_handle(
            handler: PhoneStreamHandler,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ):
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
                                "device_model": handler.device_model,
                                "battery": handler.battery_percent,
                                "temperature": handler.cpu_temperature_celsius,
                                "resolution": f"{handler.current_width}x{handler.current_height}",
                                "fps": handler.current_fps,
                                "latency": handler.average_latency,
                                "handler": handler,
                            }
                            thread.connection_changed.emit(
                                handler.config.phone_id, True, info
                            )
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
                            if hasattr(handler, "_last_nv12_frame"):
                                rgb_frame = handler.nv12_to_rgb(
                                    handler._last_nv12_frame,
                                    handler.current_width,
                                    handler.current_height,
                                )
                                thread.frame_received.emit(
                                    handler.config.phone_id, rgb_frame
                                )
                        except Exception as e:
                            logger.debug(
                                f"GUI frame error: {e}"
                            )  # Don't let GUI errors affect streaming

                    return result

                handler.process_video_frame = patched_process_video

                # Call original handler
                await original_handle(handler, reader, writer)

            except asyncio.CancelledError:
                logger.info(f"Handler for phone {handler.config.phone_id} cancelled")
                raise
            except Exception as e:
                logger.error(
                    f"Handler error for phone {handler.config.phone_id}: {e}",
                    exc_info=True,
                )
            finally:
                # Emit disconnect signal, checking if we're shutting down
                try:
                    if thread.running and not thread.shutdown_in_progress:
                        thread.connection_changed.emit(
                            handler.config.phone_id, False, {}
                        )
                        logger.debug(
                            f"Emitted disconnect for phone {handler.config.phone_id}"
                        )
                    else:
                        logger.debug(
                            f"Skipping disconnect signal for phone {handler.config.phone_id} - shutdown in progress"
                        )
                except RuntimeError as e:
                    logger.debug(f"Could not emit disconnect signal: {e}")
                except Exception as e:
                    logger.error(
                        f"Error emitting disconnect signal: {e}", exc_info=True
                    )

                # Close the writer to signal client immediately
                try:
                    if writer and not writer.is_closing():
                        writer.write_eof()  # Signal end of stream
                        await writer.drain()
                        writer.close()
                        await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
                        logger.debug(
                            f"Phone {handler.config.phone_id}: Connection closed gracefully"
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Phone {handler.config.phone_id}: Close timeout, forcing"
                    )
                except Exception as e:
                    logger.warning(
                        f"Phone {handler.config.phone_id}: Error closing connection: {e}"
                    )

        PhoneStreamHandler.handle_client = patched_handle  # type: ignore

    def update_omt_quality(self, quality_value: int):
        """Update OMT quality for all streams"""
        if self.loop and self.server:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._async_update_quality(quality_value), self.loop
                )
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Error updating OMT quality: {e}")

    async def _async_update_quality(self, quality_value: int):
        """Async wrapper for updating quality"""
        try:
            if self.server:
                self.server.update_omt_quality(quality_value)
        except Exception as e:
            logger.error(f"Error in _async_update_quality: {e}")

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
                except futures.CancelledError:
                    # This is expected when the loop is already closing
                    logger.debug("Stop task was cancelled (loop closing)")
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

                # Give a moment for cleanup
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error stopping: {e}")
