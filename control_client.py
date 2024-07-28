# -*- coding: utf-8 -*-
from threading import Thread, Event
from Exec_Cmd import Exec_Cmd
import socket

class Client_Node():
    def __init__(self) -> None:
        self.server_ip = '192.168.5.2'
        self.server_port = 51000
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((self.server_ip, self.server_port))
        self.stop_event = Event()
        self.listen_thread = Thread(target=self.listen)
        self.listen_thread.start()
        self.node_mode = 'TX'
        self.exec_cmd = Exec_Cmd()
    
    def listen(self):
        while not self.stop_event.is_set():
            encodedMessage = self.client.recv(1024)
            message = encodedMessage.decode('utf-8')
            if message == '':
                print('[CLIENT INFO] Server dead.')
                break
            print(f'[CLIENT INFO] {message}')
            if 'ack' in message:
                payload = "Orbbec_main"
                # payload, _ = self.exec_cmd.run('whoami')
                # print(f"type of payload:{type(payload)}, content:{payload}")
                self.sendText(payload)
            elif message.split(',')[0] == 'exec':
                cmd = message.split(',')[1]

                if cmd.split(' ')[0] == 'stdby':
                    self.exec_cmd.exec(cmd)

                elif cmd.split(' ')[0] == 'start':
                    cmd = cmd.replace('--', self.node_mode)
                    print(f'[CLIENT INFO] exec: {cmd}')
                    self.exec_cmd.exec(cmd)

                elif cmd.split(' ')[0] == 'stop':
                    self.exec_cmd.exec(cmd)
                    
            elif message.split(',')[0] == 'set':
                self.node_mode = message.split(',')[1]
                print(f'[CLIENT INFO] Mode changed to {self.node_mode}')

    def sendText(self, message):
        # self.client.sendall(message)
        encodedMessage = bytes(message, 'utf-8')
        self.client.sendall(encodedMessage)

    def stop(self):
        self.stop_event.set()
        self.client.close()

if __name__ == '__main__':
    client = Client_Node()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        client.stop()
        print('Client stopped.')