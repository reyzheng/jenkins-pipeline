import json

fpCue = open("dagger.cue", "w")
fpGlobal = open('settings/global_config.json')
cfgGlobal = json.load(fpGlobal)
  
for stage in cfgGlobal['stages']:
    print(stage)
    print("# This is a testing!", file=fpCue)
 
# Closing file
fpGlobal.close()
fpCue.close()
