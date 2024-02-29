import pytest
import re
from qontrol import *
from virtual_module import *
from glob import glob
import random

class TestCommandIndex:
    """
    Test the CmdIndex Enum and its asocciated methods
    """

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_unsupported_header_mode(self, c):
        """
        Test that command index doesn't support
        header modes it shouldn't.

        Test one at a time. 
        """
        unsupported_header_modes = set(HeaderMode) - c.header_modes()
        for uhm in unsupported_header_modes:
            assert not c.supports(uhm)

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_unsupported_header_mode_all(self, c):
        """
        Test that command index doesn't support
        header modes it shouldn't.

        Test all at the same time
        """
        unsupported_header_modes = set(HeaderMode) - c.header_modes()
        assert not c.supports(unsupported_header_modes)

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_supported_header_mode(self, c):
        """
        Test that command index supports all modes.

        Test one at a time
        """
        for hm in c.header_modes():
            assert c.supports(hm)

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_supported_header_mode_all(self, c):
        """
        Test that command index supports all modes.

        Test all at the same time
        """
        c.supports(c.header_modes())

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_supports_header_mode_mixed(self, c):
        """
        Test that cmdidx.supports() correctly returns False
        when passing in a mixture of supported and unsupported modes.
        """
        unsupported_header_modes = set(HeaderMode) - c.header_modes()

        for uhm in unsupported_header_modes:
            assert not c.supports(*c.header_modes(), uhm)

            

def cmds_supporting(header_mode):
    return [c for c in CmdIndex if c.supports(header_mode)]    
    
class TestBinaryCommand:
    """
    Test the Command class and its asocciated methods
    """

    N_CH = 1024
    N_RANDOM = 10000
    MAX_DATA_SIZE = 100
    
    def expected_binary(self, cmd):
        """
        Old Binary command generation.
        
        Used to validate the new method.
        """

        # Set the old parameters from the command
        command_id = cmd.idx.code()
        ch = cmd.addr
        BCAST = int(Header.BCAST in cmd.header)
        ALLCH = int(Header.ALLCH in cmd.header)
        ADDM = int(Header.ADDM in cmd.header)
        RW = int(Header.RW in cmd.header)
        ACT = int(Header.ACT in cmd.header)
        DEXT = int(Header.DEXT in cmd.header)
        value_int = cmd.data
        addr_id_num = cmd.addr_id


        def get_val(i):
                """Function to convert uint16 to bytearray([uint8,uint8])"""
                return bytearray([int(i/256),int(i)-int(i/256)*256])

        def parity_odd(x):
                """Function to compute whether a byte's parity is odd."""
                x = x ^ (x >> 4)
                x = x ^ (x >> 2)
                x = x ^ (x >> 1)
                return x & 1


        # Format header byte
        header_byte  =       0x80
        header_byte += BCAST*0x40
        header_byte += ALLCH*0x20
        header_byte +=  ADDM*0x10
        header_byte +=    RW*0x08
        header_byte +=   ACT*0x04
        header_byte +=  DEXT*0x02
        header_byte += parity_odd(header_byte)


        # Format command byte
        if isinstance(command_id, str):
            command_byte = CMD_CODES[command_id.upper()]
        elif isinstance(command_id, int):
            command_byte = command_id


        # Format channel address
        address_bytes = bytearray()
        if ch is None:
            ch = 0
        if ADDM == 1:
            address_bytes.extend(get_val(addr_id_num))
            address_bytes.append(ch)
        elif ADDM == 0:
            address_bytes.append(0)
            address_bytes.extend(get_val(ch))


        # Format value bytes
        # value_int can be either an int or a list of ints (for vectorised input, DEXT = 1)
        data_bytes = bytearray()

        if DEXT == 1:
            # Handle data extension length
            if isinstance(value_int, list):
                n_dext_words = len(value_int)
            else:
                n_dext_words = 1
            if n_dext_words > 0xFFFF:
                n_dext_words = 0xFFFF
            data_bytes.extend(get_val(n_dext_words))

        if isinstance(value_int, int):
            v = get_val(value_int)

            data_bytes.extend(get_val(value_int))

        elif isinstance(value_int, list) and all([isinstance(e ,int) for e in value_int]):
            for i,e in enumerate(value_int):
                data_bytes.extend(get_val(e))
                if i == n_dext_words:
                    break

        else:
            raise AttributeError("value_int must be of type int,\
                                 or of type list with all elements of type\
                                 int (received type {:})".format(type(value_int) ) )


        # Compose command byte string
        tx_str = bytearray()
        tx_str.append(header_byte) # Header byte
        tx_str.append(command_byte) # Command byte
        tx_str.extend(address_bytes) # Three bytes of channel address
        tx_str.extend(data_bytes) # 2 (DEXT=0) or 2*N+1 (DEXT=1) bytes of data

        # Transmit it
        return tx_str

    ###########################################################
    # Test Read commands ADDM = 0
    ###########################################################
    
    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_no_ch(self, c):
        cmd = Command(c)
        assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_random(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            # ch is 16 bits 
            ch = random.randint(0, 2**16 - 1)
            cmd = Command(c, addr=ch)
            assert cmd.binary() == self.expected_binary(cmd)
            
    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_min(self, c):
        cmd = Command(c, addr=0)
        assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_max(self, c):
        cmd = Command(c, addr= 2**16 - 1)
        assert cmd.binary() == self.expected_binary(cmd)


    @pytest.mark.parametrize('c', cmds_supporting(READ_ALLCH))
    def test_read_allch_cmd_binary(self, c):
        cmd = Command(c, header=ALLCH)
        assert cmd.binary() == self.expected_binary(cmd)

        

    ###########################################################
    # Test Read commands  ADDM = 1
    ###########################################################
    
    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_no_ch_addm(self, c):
        cmd = Command(c, header=ADDM)
        assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_random_addm(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            # Addr id is 16 bits 
            dev_id = random.randint(0, 2**16 - 1)

            # Channel is 8 bits
            ch = random.randint(0, 2**8 - 1)
         
            cmd = Command(c, addr=ch, addr_id=dev_id, header=ADDM)
            assert cmd.binary() == self.expected_binary(cmd)


    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_min_addm(self, c):
        cmd = Command(c, addr=0, addr_id=0)
        assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_ch_max_addm(self, c):
        cmd = Command(c, addr= 2**8 - 1, addr_id= 2**16 - 1)
        assert cmd.binary() == self.expected_binary(cmd)

        
    @pytest.mark.parametrize('c', cmds_supporting(READ_ALLCH))
    def test_read_allch_cmd_binary_addm(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            dev_id = random.randint(0, 2**16 - 1)
            cmd = Command(c, header=ALLCH | ADDM, addr_id=dev_id)
            assert cmd.binary() == self.expected_binary(cmd)

    ###########################################################
    # Test Write commands  ADDM = 0
    ###########################################################
            
    @pytest.mark.parametrize('c', cmds_supporting(WRITE))
    def test_write_cmds_single_channel_single_data(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            ch = random.randint(0, 2**16 - 1)
            data = random.randint(0, 2**16 - 1)

            cmd = Command(c, addr=ch, data=data)
            assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(WRITE_DEXT))
    def test_write_cmds_single_channel_list_data(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            ch = random.randint(0, 2**16 - 1)

            size = random.randint(0, TestBinaryCommand.MAX_DATA_SIZE)
            data = [random.randint(0, 2**16 - 1) for _ in range(size)]

            cmd = Command(c, addr=ch, data=data, header = DEXT)
            assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(WRITE_ALLCH))
    def test_write_cmds_all_ch(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            ch = random.randint(0, 2**16 - 1)
            data = random.randint(0, 2**16 - 1)

            cmd = Command(c, data=data, header=ALLCH)
            assert cmd.binary() == self.expected_binary(cmd)


    ###########################################################
    # Test Write commands  ADDM = 1
    ###########################################################
            
    @pytest.mark.parametrize('c', cmds_supporting(WRITE))
    def test_write_cmds_single_channel_single_data_addm(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            dev_id = random.randint(0, 2**16 - 1)
            ch = random.randint(0, 2**8 - 1)
            data = random.randint(0, 2**16 - 1)

            cmd = Command(c, addr=ch, addr_id=dev_id,
                          data=data, header = ADDM)
            assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(WRITE_DEXT))
    def test_write_cmds_single_channel_list_data_addm(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            ch = random.randint(0, 2**8 - 1)
            dev_id = random.randint(0, 2**16 - 1)

            size = random.randint(0, TestBinaryCommand.MAX_DATA_SIZE)
            data = [random.randint(0, 2**16 - 1) for _ in range(size)]

            cmd = Command(c, addr=ch, addr_id=dev_id,
                          data=data, header = DEXT | ADDM)
            assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', cmds_supporting(WRITE_ALLCH))
    def test_write_cmds_all_ch_addm(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            dev_id = random.randint(0, 2**16 - 1)
            data = random.randint(0, 2**16 - 1)

            cmd = Command(c, addr_id=dev_id, data=data, header=ALLCH | ADDM)
            assert cmd.binary() == self.expected_binary(cmd)


    ###########################################################
    # Test ACT commands  ADDM = 1
    ###########################################################
    @pytest.mark.parametrize('c', cmds_supporting(ACT_M))
    def test_act_cmds(self, c):
        cmd = Command(c)
        assert cmd.binary() == self.expected_binary(cmd)

    ###########################################################
    # Test All Headers
    ###########################################################
    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_all_cmds_all_headers_single(self, c):

        for h in Header:
            if h == DEXT:
                cmd = Command(c, header=h, data=[0])
            else:
                 cmd = Command(c, header=h)
                 
            assert cmd.binary() == self.expected_binary(cmd)

    @pytest.mark.parametrize('c', [cmd for cmd in CmdIndex])
    def test_all_cmds_all_headers_random(self, c):
        for _ in range(TestBinaryCommand.N_RANDOM):
            size = random.randint(0, len(Header))
            h = reduce(lambda x, y: x | y, random.sample(list(Header), size), BIN)
            
            if DEXT in h:
                cmd = Command(c, header=h, data=[0])
            else:
                 cmd = Command(c, header=h)
                 
            assert cmd.binary() == self.expected_binary(cmd)


class TestASCIICommand:
    """
    Test the Command class and its asocciated methods
    """

    N_CH = 1024
    N_RANDOM = 10000
    MAX_DATA_SIZE = 100
    
    def expected_ascii (self, cmd):

        """
        """

        command_id= cmd.idx
        ch=cmd.addr
        operator=cmd.type().value
        value=cmd.data
        
        # Check for previous errors
        lines,errs = self.receive()

        # Transmit command
        if ch is None:
            ch = ''
        if value is None:
            value = ''
        if isinstance(value,list):
            tx_str = '{0}{1}{2}{3}'.format(command_id, ch, operator,value[0])
            for v in value[1:]:
                tx_str += ',{:}'.format(v)
        else:
            tx_str = '{0}{1}{2}{3}'.format(command_id, ch, operator, value)

        return tx_str+'\n'

    ###########################################################
    # Test Read commands ADDM = 0
    ###########################################################
    
    @pytest.mark.parametrize('c', cmds_supporting(READ))
    def test_read_cmd_binary_no_ch(self, c):
        cmd = Command(c)
        assert cmd.ascii() == self.expected_ascii(cmd)

    # @pytest.mark.parametrize('c', cmds_supporting(READ))
    # def test_read_cmd_binary_ch_random(self, c):
    #     for _ in range(TestBinaryCommand.N_RANDOM):
    #         # ch is 16 bits 
    #         ch = random.randint(0, 2**16 - 1)
    #         cmd = Command(c, addr=ch)
    #         assert cmd.binary() == self.expected_binary(cmd)
            
    # @pytest.mark.parametrize('c', cmds_supporting(READ))
    # def test_read_cmd_binary_ch_min(self, c):
    #     cmd = Command(c, addr=0)
    #     assert cmd.binary() == self.expected_binary(cmd)

    # @pytest.mark.parametrize('c', cmds_supporting(READ))
    # def test_read_cmd_binary_ch_max(self, c):
    #     cmd = Command(c, addr= 2**16 - 1)
    #     assert cmd.binary() == self.expected_binary(cmd)


    # @pytest.mark.parametrize('c', cmds_supporting(READ_ALLCH))
    # def test_read_allch_cmd_binary(self, c):
    #     cmd = Command(c, header=ALLCH)
    #     assert cmd.binary() == self.expected_binary(cmd)

    ###########################################################
    # Test Write commands  ADDM = 0
    ###########################################################
            
    # @pytest.mark.parametrize('c', cmds_supporting(WRITE))
    # def test_write_cmds_single_channel_single_data(self, c):
    #     for _ in range(TestBinaryCommand.N_RANDOM):
    #         ch = random.randint(0, 2**16 - 1)
    #         data = random.randint(0, 2**16 - 1)

    #         cmd = Command(c, addr=ch, data=data)
    #         assert cmd.binary() == self.expected_binary(cmd)

    # @pytest.mark.parametrize('c', cmds_supporting(WRITE_DEXT))
    # def test_write_cmds_single_channel_list_data(self, c):
    #     for _ in range(TestBinaryCommand.N_RANDOM):
    #         ch = random.randint(0, 2**16 - 1)

    #         size = random.randint(0, TestBinaryCommand.MAX_DATA_SIZE)
    #         data = [random.randint(0, 2**16 - 1) for _ in range(size)]

    #         cmd = Command(c, addr=ch, data=data, header = DEXT)
    #         assert cmd.binary() == self.expected_binary(cmd)

    # @pytest.mark.parametrize('c', cmds_supporting(WRITE_ALLCH))
    # def test_write_cmds_all_ch(self, c):
    #     for _ in range(TestBinaryCommand.N_RANDOM):
    #         ch = random.randint(0, 2**16 - 1)
    #         data = random.randint(0, 2**16 - 1)

    #         cmd = Command(c, data=data, header=ALLCH)
    #         assert cmd.binary() == self.expected_binary(cmd)



    

