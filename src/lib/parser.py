import argparse

def get_parser(parser_type: str):
    description = ""
    usage = ""
    if parser_type == "server":
        description = "Server for file transfer application"
        usage = "start-server [-h] [-v | -q] [-H ADDR] [-p PORT] [-s DIRPATH]"
    elif parser_type == "upload":
        description = "Client to upload a file to the server"
        usage = "upload [-h] [-v | -q] [-H ADDR] [-p PORT] [-s FILEPATH] [-n FILENAME] [-r protocol]"
    elif parser_type == "download":
        description = "Client to download a file from the server"
        usage = "download [-h] [-v | -q] [-H ADDR] [-p PORT] [-d FILEPATH] [-n FILENAME] [-r protocol]"

    parser = argparse.ArgumentParser(description=description, usage=usage)

    # args comunes
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")

    parser.add_argument("-H", "--host", metavar="", help="IP address")
    parser.add_argument("-p", "--port", type=int, metavar="", help="port")
    
    # args específicos
    if parser_type == "server":
        parser.add_argument("-s", "--storage", metavar="", help="storage dir path")
    
    elif parser_type == "upload":
        parser.add_argument("-s", "--src", metavar="", help="source file path")
        parser.add_argument("-n", "--name", metavar="", help="file name")
        parser.add_argument("-r", "--protocol", metavar="", help="error recovery protocol")
        
    elif parser_type == "download":
        parser.add_argument("-d", "--dst", metavar="", help="destination file path")
        parser.add_argument("-n", "--name", metavar="", help="file name")
        parser.add_argument("-r", "--protocol", metavar="", help="error recovery protocol")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()