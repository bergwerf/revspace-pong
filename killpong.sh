#!/bin/bash

netstat -nltp | grep "0.0.0.0:8000" | awk '{print $7}' | awk -F '/' '{print $1}' | xargs kill
