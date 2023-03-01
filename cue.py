import json

fpGlobal = open('settings/global_config.json')
cfgGlobal = json.load(fpGlobal)
  
for stage in cfgGlobal['stages']:
    print(stage)
  
# Closing file
fpGlobal.close()
