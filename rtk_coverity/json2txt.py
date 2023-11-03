import getopt, sys
import json

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "i:", ["input="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        #usage()
        sys.exit(2)
    input = None
    verbose = False
    for o, a in opts:
        if o in ("-i", "--input"):
            input = a
        else:
            assert False, "unhandled option"

    with open(input) as f:
        data = json.load(f)
    f.close()
    
    fp = open("checkers", "w")
    fp.write(data["default"]["options"])
    fp.close()

if __name__ == "__main__":
    main()