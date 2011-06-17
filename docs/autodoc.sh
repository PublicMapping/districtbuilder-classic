#!/bin/bash

# Generate the HTML and class UML diagrams
epydoc --config=epydoc.config

# Generate the DOT code for graphviz. This will prompt for a password
echo "Password for database 'publicmapping':"
postgresql_autodoc -d publicmapping2 -h localhost -p 5432 -u publicmapping --password -s publicmapping -m "redistricting_" -t dot

# Generate a graphic from the dot file.
dot -Tpng publicmapping2.dot -o html/schema.png

rm publicmapping2.dot
cp html/schema.png schema.png
