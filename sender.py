from packet import *
from socket import *
from threading import *
import sys

MAX_WINDOW_SIZE = 10
MAX_DATA_LENGTH = 500
SEQ_NUM_MODULO = 32

global sendSocket, seqOut, ackOut


class sender:
    send_packets = {}
    send_base = 0
    seq_num = 0
    next_seq_num = 0
    timer = None

    send_complete = False
    receive_complete = False

    def __init__(self, emulator_address, emulator_port, sender_port, input_file_name):
        self.emulator_address = emulator_address
        self.emulator_port = emulator_port
        self.sender_port = sender_port
        self.input_file_name = input_file_name

    def seq_range(self, start, end):
        res = []
        for i in range(start, end):
            res.append(i)
        return res

    def send_thread(self):
        file = open(self.input_file_name)

        while not self.receive_complete:
            content = file.read(MAX_DATA_LENGTH)

            if content == '':
                self.send_complete = True
                break

            p = packet.create_packet(self.next_seq_num, content)
            self.send_packets[self.next_seq_num] = p

            cv.acquire()

            while self.wait():
                cv.wait()

            sendSocket.sendto(p.get_udp_data(), (self.emulator_address, self.emulator_port))
            seqOut.write("%d\n" % p.seq_num)

            if self.next_seq_num == self.send_base:
                self.timer_start()

            self.next_seq_num += 1
            self.next_seq_num %= SEQ_NUM_MODULO

            cv.release()

        file.close()

    def wait(self):
        window_end = self.send_base + MAX_WINDOW_SIZE

        if window_end < SEQ_NUM_MODULO:
            if self.next_seq_num < self.send_base or self.next_seq_num >= window_end:
                return True
        elif (window_end % SEQ_NUM_MODULO <= self.next_seq_num) and (self.next_seq_num < self.send_base):
            return True
        else:
            return False

    def receive_thread(self):
        while True:
            data, _ = sendSocket.recvfrom(512)
            receive_packet = packet.parse_udp_data(data)
            if receive_packet.type != 2:
                ackOut.write("%d\n" % receive_packet.seq_num)
            else:
                self.receive_complete = True
                break

            cv.acquire()

            self.send_base = (receive_packet.seq_num + 1) % SEQ_NUM_MODULO

            if self.next_seq_num == self.send_base:
                self.timer.cancel()
                if self.send_complete:
                    eot = packet.create_eot(self.next_seq_num)
                    sendSocket.sendto(eot.get_udp_data(), (self.emulator_address, self.emulator_port))
            else:
                self.timer_start()

            cv.notify()
            cv.release()

        seqOut.close()
        ackOut.close()
        sendSocket.close()

    def resend(self):
        cv.acquire()
        self.timer_start()

        if self.next_seq_num <= self.send_base:
            send_seq = self.seq_range(0, self.next_seq_num) + self.seq_range(self.send_base, SEQ_NUM_MODULO)
        else:
            send_seq = self.seq_range(self.send_base, self.next_seq_num)

        for i in send_seq:

            p = self.send_packets[i]
            sendSocket.sendto(p.get_udp_data(), (self.emulator_address, self.emulator_port))
            seqOut.write("%d\n" % p.seq_num)

        cv.release()

    def timer_start(self):
        if self.timer is not None:
            self.timer.cancel()
        self.timer = Timer(0.1, self.resend)
        self.timer.start()


if __name__ == "__main__":
    # If incorrect number of arguments passed in, print error and exit the program
    if len(sys.argv) != 5:
        print ("usage: python3 sender.py <host address of the network emulator>, \n" +
               "<UDP port number used by the emulator to receive data from the sender>, \n" +
               "<UDP port number used by the sender to receive ACKs from the emulator>, \n" +
               "<name of the file to be transferred>")
        sys.exit(1)

    # parse input from arguments
    emulator_address = sys.argv[1]
    emulator_port = int(sys.argv[2])
    sender_port = int(sys.argv[3])
    input_file_name = sys.argv[4]

    sendSocket = socket(AF_INET, SOCK_DGRAM)
    sendSocket.bind(('', sender_port))

    seqOut = open("seqnum.log", "w")
    ackOut = open("ack.log", "w")

    sender = sender(emulator_address, emulator_port, sender_port, input_file_name)

    lock = Lock()
    cv = Condition(lock=lock)

    thread1 = Thread(target=sender.send_thread)
    thread2 = Thread(target=sender.receive_thread)

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
