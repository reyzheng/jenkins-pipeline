# coverity.py

def coverity(configFile):
    print("config {}".format(configFile))

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(argv, "c:")  
    except:
        print("Error")
  
    for opt, arg in opts:
        if opt in ['-c']:
            config = arg

    coverity(config)