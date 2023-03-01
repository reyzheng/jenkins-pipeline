import json

fpCue = open("dagger.cue", "w")
fpGlobal = open('settings/global_config.json')
cfgGlobal = json.load(fpGlobal)
  
for stage in cfgGlobal['stages']:
    print(stage)
    print >>fpCue, "This is a testing!"
 
# Closing file
fpGlobal.close()
fpCue.close()
