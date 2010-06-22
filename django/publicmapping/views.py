from django.shortcuts import render_to_response
import random

def index(request):
    width = 140024
    height = 42007
    xmin = -9439758
    ymin = 4804742
    xmax = -9017448 - width
    ymax = 5069106 - height

    xmin = random.uniform( xmin, xmax )
    ymin = random.uniform( ymin, ymax )
    xmax = xmin + width
    ymax = ymin + height

    bbox = "%d,%d,%d,%d" % ( xmin, ymin, xmax, ymax )

    return render_to_response('index.html', { 'bbox': bbox })
