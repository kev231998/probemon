#!/bin/bash

# helper script to update all things related to protobuf proto

protoc --python_out=. probe.proto
protoc --js_out=import_style=commonjs,binary:static/js probe.proto

cd static/js
if [[ ! -d node_modules ]]; then
	npm install
fi
npm run build
