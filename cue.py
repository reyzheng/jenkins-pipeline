import json

fpCue = open("dagger.cue", "w")
fpGlobal = open('settings/global_config.json')
cfgGlobal = json.load(fpGlobal)

print("// usage: dagger-cue do hello --log-format=plain", file=fpCue)
print("package helloworld", file=fpCue)
print("import (", file=fpCue)
print("    \"dagger.io/dagger\"", file=fpCue)
print("    \"dagger.io/dagger/core\"", file=fpCue)
print(")", file=fpCue)
print("dagger.#Plan & {", file=fpCue)
print("    client: env: GREETING: string | *\"hello\"", file=fpCue)
print("    actions: {", file=fpCue)
print("        image: core.#Pull & {", file=fpCue)
print("            source: \"alpine:3\"", file=fpCue)
print("        }", file=fpCue)
print("        hello: core.#Exec & {", file=fpCue)
print("            input: image.output", file=fpCue)
print("            args: [\"echo\", \"\(client.env.GREETING), world!\"]", file=fpCue)
print("            always: true", file=fpCue)
print("        }", file=fpCue)
print("        hello2: core.#Exec & {", file=fpCue)
print("            input: image.output", file=fpCue)
print("            args: [\"pwd\"]", file=fpCue)
print("            always: true", file=fpCue)
print("        }", file=fpCue)
print("    }", file=fpCue)
print("}", file=fpCue)

for stage in cfgGlobal['stages']:
    print(stage)
 
# Closing file
fpGlobal.close()
fpCue.close()
