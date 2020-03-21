from packet import *
from socket import *
from threading import *
import sys

MAX_WINDOW_SIZE = 10
MAX_DATA_LENGTH = 500
SEQ_NUM_MODULO = 32


class sender:
    seqOut = None

    sendPackets = {}
    base = 0
    seqNum = 0
    nextSeqNum = 0

    sendSocket = None
    timer = None

    end = False

    def __init__(self, emulatorAddress, emulatorPort, senderPort, inputFileName):
        self.emulatorAddress = emulatorAddress
        self.emulatorPort = emulatorPort
        self.senderPort = senderPort
        self.inputFileName = inputFileName
        # initiate udp socket
        self.sendSocket = socket(AF_INET, SOCK_DGRAM)
        self.sendSocket.bind(('', self.senderPort))

        # open log files
        self.seqOut = open("seqnum.log", "w")

    # resend sent but not acked packets
    def resend(self):
        cv.acquire()
        self.setTimer()
        if self.nextSeqNum > self.base:
            for i in range(self.base, self.nextSeqNum):
                self.send_packet(i)
        else:
            for i in range(self.base, SEQ_NUM_MODULO):
                self.send_packet(i)
            for i in range(0, self.nextSeqNum):
                self.send_packet(i)

        cv.release()

    # helper to send data packet with seqnum i
    def send_packet(self, i):
        data = self.sendPackets[i].get_udp_data()
        self.sendSocket.sendto(data, (self.emulatorAddress, self.emulatorPort))
        self.seqOut.write(str(i) + "\n")

    # function to send packets
    def send_packets(self):
        file = open(self.inputFileName)

        while True:
            content = file.read(MAX_DATA_LENGTH)

            # if reach end of file, close input file and break
            if content == '':
                file.close()
                self.end = True
                break

            cv.acquire()

            while self.wait():
                cv.wait()

            # send packets
            p = packet.create_packet(self.nextSeqNum, content)
            self.sendSocket.sendto(p.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
            self.seqOut.write(str(self.nextSeqNum) + "\n")
            self.sendPackets[self.nextSeqNum] = p

            # start timer when there's no unacked packet
            if self.nextSeqNum == self.base:
                self.setTimer()
            self.nextSeqNum += 1
            self.nextSeqNum %= SEQ_NUM_MODULO

            cv.release()

    def wait(self):
        outbound = self.base + MAX_WINDOW_SIZE
        if outbound >= SEQ_NUM_MODULO:
            outbound = outbound % SEQ_NUM_MODULO
            if outbound <= self.nextSeqNum < self.base:
                return True
        else:
            if self.nextSeqNum < self.base or self.nextSeqNum >= outbound:
                return True
        return False

    # function to receive ack packets
    def receive_ack(self):
        ackOut = open("ack.log", "w")
        while True:
            # receive packet
            data, addr = self.sendSocket.recvfrom(512)
            receivePacket = packet.parse_udp_data(data)
            if receivePacket.type == 2:
                break

            cv.acquire()

            # update base and log when receive ack
            self.base = (receivePacket.seq_num + 1) % SEQ_NUM_MODULO
            ackOut.write(str(receivePacket.seq_num) + "\n")

            if self.nextSeqNum == self.base:
                # stop timer and send EOT when all sent packets are acknowledged
                self.timer.cancel()
                # if self.end:
                eot = packet.create_eot(self.base)
                self.sendSocket.sendto(eot.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
            else:
                # if there are still packet sent but no acknowledged, reset timer
                self.setTimer()

            cv.notify()
            cv.release()

        self.seqOut.close()
        ackOut.close()
        self.sendSocket.close()

    # function to set timer
    def setTimer(self):
        if self.timer is not None:
            # stop timer when a packet is acked
            self.timer.cancel()
        # start timer and schedule resent task after 100ms
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
    emulatorAddress = sys.argv[1]
    emulatorPort = int(sys.argv[2])
    senderPort = int(sys.argv[3])
    inputFileName = sys.argv[4]

    sender = sender(emulatorAddress, emulatorPort, senderPort, inputFileName)

    # initialize lock and condition variable
    lock = Lock()
    cv = Condition(lock=lock)

    # create two threads, one for sending data packet,  one for receiving ack packets
    thread1 = Thread(target=sender.send_packets)
    thread2 = Thread(target=sender.receive_ack)

    # start two threads and join
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
