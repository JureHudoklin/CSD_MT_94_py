import threading
import queue
import types
import time
from pymodbus.client import ModbusTcpClient


class ThreadSafeClientWrapper:
    def __init__(self, client: ModbusTcpClient):
        self.exit = False
        
        self._client = client
        self.command_queue = queue.Queue()
        self.result_dict = {}
        self.lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        self.last_used = time.time()

    def _worker(self):
        while not self.exit:
            if self.command_queue.empty() and self._client.is_socket_open():
                if time.time() - self.last_used > 1:
                    self._client.close()
                    self.last_close = time.time()
                time.sleep(0.05)
            elif not self.command_queue.empty() and not self._client.is_socket_open():
                self._client.connect()
                self.last_used = time.time()
            
            command, args, kwargs, result_event = self.command_queue.get()
            try:
                result = getattr(self._client, command)(*args, **kwargs)
                with self.lock:
                    self.result_dict[result_event] = result
                result_event.set()
            except Exception as e:
                with self.lock:
                    self.result_dict[result_event] = e
                result_event.set()
            finally:
                self.command_queue.task_done()
                
    def execute_command(self, command, *args, **kwargs):
        result_event = threading.Event()
        self.command_queue.put((command, args, kwargs, result_event))
        result_event.wait()
        
        with self.lock:
            result = self.result_dict.pop(result_event)
        
        if isinstance(result, Exception):
            raise result
        return result

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.execute_command(name, *args, **kwargs)
    
    def __del__(self):
        self.exit_ = True
        if self.worker_thread.is_alive():
            self.worker_thread.join()
        self._client.close()
        
    def stop(self):
        self.exit_ = True
