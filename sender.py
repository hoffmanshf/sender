from packet import *
from socket import *
from threading import *
import sys

MAX_WINDOW_SIZE = 10
MAX_DATA_LENGTH = 500
SEQ_NUM_MODULO = 32

global sendSocket, seqOut, ackOut


class sender:
    sendPackets = {}
    base = 0
    seqNum = 0
    nextSeqNum = 0
    timer = None

    def __init__(self, emulatorAddress, emulatorPort, senderPort, inputFileName):
        self.emulatorAddress = emulatorAddress
        self.emulatorPort = emulatorPort
        self.senderPort = senderPort
        self.inputFileName = inputFileName

    def send_packets(self):
        file = open(self.inputFileName)

        while True:
            content = file.read(MAX_DATA_LENGTH)

            if content == '':
                break

            p = packet.create_packet(self.nextSeqNum, content)
            self.sendPackets[self.nextSeqNum] = p

            cv.acquire()

            while self.wait():
                cv.wait()

            sendSocket.sendto(p.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
            seqOut.write("%d\n" % p.seq_num)

            if self.nextSeqNum == self.base:
                self.setTimer()

            self.nextSeqNum += 1
            self.nextSeqNum %= SEQ_NUM_MODULO

            cv.release()

        file.close()

    def wait(self):
        windowEnd = self.base + MAX_WINDOW_SIZE

        if windowEnd < SEQ_NUM_MODULO:
            if self.nextSeqNum < self.base or self.nextSeqNum >= windowEnd:
                return True
        elif windowEnd % SEQ_NUM_MODULO <= self.nextSeqNum < self.base:
            return True
        else:
            return False

    def receive_ack(self):
        while True:
            data, addr = sendSocket.recvfrom(512)
            receivePacket = packet.parse_udp_data(data)
            if receivePacket.type != 2:
                ackOut.write("%d\n" % receivePacket.seq_num)
            else:
                break

            cv.acquire()

            self.base = (receivePacket.seq_num + 1) % SEQ_NUM_MODULO

            if self.nextSeqNum == self.base:
                self.timer.cancel()
                eot = packet.create_eot(self.base)
                sendSocket.sendto(eot.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
            else:
                self.setTimer()

            cv.notify()
            cv.release()

        seqOut.close()
        ackOut.close()
        sendSocket.close()

    def resend(self):
        cv.acquire()
        self.setTimer()
        resendPackets = {}
        idx = 0
        if self.nextSeqNum > self.base:
            for i in range(self.base, self.nextSeqNum):
                resendPackets[idx] = self.sendPackets[i]
                idx += 1
        else:
            for i in range(0, self.nextSeqNum):
                resendPackets[idx] = self.sendPackets[i]
                idx += 1
            for i in range(self.base, SEQ_NUM_MODULO):
                resendPackets[idx] = self.sendPackets[i]
                idx += 1

        for p in resendPackets.values():
            sendSocket.sendto(p.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
            seqOut.write("%d\n" % p.seq_num)

        cv.release()

    def setTimer(self):
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
    emulatorAddress = sys.argv[1]
    emulatorPort = int(sys.argv[2])
    senderPort = int(sys.argv[3])
    inputFileName = sys.argv[4]

    sendSocket = socket(AF_INET, SOCK_DGRAM)
    sendSocket.bind(('', senderPort))

    seqOut = open("seqnum.log", "w")
    ackOut = open("ack.log", "w")

    sender = sender(emulatorAddress, emulatorPort, senderPort, inputFileName)

    lock = Lock()
    cv = Condition(lock=lock)

    thread1 = Thread(target=sender.send_packets)
    thread2 = Thread(target=sender.receive_ack)

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()
