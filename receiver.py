from packet import *
from socket import *
import sys

MAX_DATA_LENGTH = 500
SEQ_NUM_MODULO = 32
MAX_WINDOW_SIZE = 10


class receiver:

    def __init__(self, emulatorAddress, emulatorPort, receiverPort, outputFileName):
        self.emulatorAddress = emulatorAddress
        self.emulatorPort = emulatorPort
        self.receiverPort = receiverPort
        self.outputFileName = outputFileName

    def receive(self):
        # establish UDP socket connection
        receiveSocket = socket(AF_INET, SOCK_DGRAM)
        receiveSocket.bind(('', self.receiverPort))
        sendSocket = socket(AF_INET, SOCK_DGRAM)

        arrivalOut = open("arrival.log", "w")
        fileOut = open(self.outputFileName, "w")

        expectedSeq = 0
        prevExpectedSeq = -1

        while True:
            # receive data packet from the emulator
            data, addr = receiveSocket.recvfrom(512)
            # parse packet data to packet object
            receivePacket = packet.parse_udp_data(data)
            # get received seqnum from the packet
            receivedSeq = receivePacket.seq_num
            # write seqnum to arrival.log
            if receivePacket.type != 2:
                arrivalOut.write(str(receivedSeq) + "\n")

            # check if received seqnum equals to expected seqnum
            if receivedSeq == expectedSeq:
                # write data to the output file if received packet is data packet
                if receivePacket.type == 1:
                    fileOut.write(str(receivePacket.data))

                # increment expected seqnum
                expectedSeq += 1
                # limit the seqnum to maximum of 32
                expectedSeq %= SEQ_NUM_MODULO
                prevExpectedSeq = expectedSeq

            # do nothing till first packet is received
            if prevExpectedSeq != -1:
                # update received seq number is different from expected seq number
                receivedSeq = (expectedSeq - 1) % SEQ_NUM_MODULO if receivedSeq != expectedSeq else receivedSeq
                if receivePacket.type == 1:
                    # send ack packet to the emulator if data packet received
                    ackDataPacket = packet.create_ack(receivedSeq)
                    sendSocket.sendto(ackDataPacket.get_udp_data(), (self.emulatorAddress, self.emulatorPort))
                if receivePacket.type == 2:
                    # send eot packet to confirm with emulator if received eot packet from sender
                    eotDataPacket = packet.create_eot(receivedSeq)
                    sendSocket.sendto(eotDataPacket.get_udp_data(), (self.emulatorAddress, self.emulatorPort))

                    # close connection and exit the program
                    fileOut.close()
                    arrivalOut.close()
                    receiveSocket.close()
                    sendSocket.close()
                    return


if __name__ == "__main__":
    # If incorrect number of arguments passed in, print error and exit the program
    if len(sys.argv) != 5:
        print ("usage: python3 receiver.py <host address of the network emulator>, \n" +
               "<UDP port number used by the emulator to receive ACKs from the receiver>, \n" +
               "<UDP port number used by the receiver to receive data from the emulator>, \n" +
               "<name of the file into which the received data is written>")
        sys.exit(1)

    # parse input from arguments
    emulatorAddress = sys.argv[1]
    emulatorPort = int(sys.argv[2])
    receiverPort = int(sys.argv[3])
    outputFileName = sys.argv[4]

    receiver = receiver(emulatorAddress, emulatorPort, receiverPort, outputFileName)
    receiver.receive()
