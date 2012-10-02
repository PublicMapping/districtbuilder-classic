#!/bin/bash

if [ "x`which epydoc`" == "x" ]; then
    echo ""
    echo "This tool requires 'epydoc' to be installed."
    echo "You can install this utility with the command: 'pip install epydoc'"
    echo ""
    exit 1
fi

if [ "x`which dot`" == "x" ]; then
    echo ""
    echo "This tool requires 'graphviz' to be installed."
    echo "You can install this utility with the command: 'apt-get install graphviz'"
    echo ""
    exit 2
fi

# Generate the HTML and class UML diagrams
epydoc --config=epydoc.config
