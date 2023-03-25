# coverity.py
import getopt
import sys

def coverity(configFile):
    print("config {}".format(configFile))

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c:", ["config="])
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
  
    for opt, arg in opts:
        if opt in ['-c']:
            config = arg

    coverity(config)