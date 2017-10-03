/*
   Copyright 2010 Micah Altman, Michael McDonald

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   This file is part of The Public Mapping Project
   https://github.com/PublicMapping/

   Purpose:
       This script file contains a utility object that sorts a table
       based on its contents.

   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * sorting tables.
 *
 * Parameters:
 *   options -- Configuration options for the table sorter.
 */
viewablesorter = function(options) {

    /*
    * A sort function that sorts all items visible on the map above those 
    * that are not visible.  Numbered sortNames after that in numeric 
    * order, and alpha names sorted alphabetically after that.
    *
    * This element expects the jQuery data attribute on each data row 
    * to have an "isVisibleOnMap" attribute and a "sortableName" attribute.
    */
    var viewableSort = function(rowA, rowB) {
        var aScore = 0, bScore = 0;
        var a = $(rowA);
        var b = $(rowB);
        if (a.data('isVisibleOnMap') == true) {
            aScore -= 1000;
        }
        if (b.data('isVisibleOnMap') == true) {
            bScore -= 1000;
        }
        aName = a.children('.district_name').text();
        bName = b.children('.district_name').text();
        aNum = parseInt(aName);
        bNum = parseInt(bName);

        // Always show the unassigned district on top
        if (aName == '\xD8') {
            aScore = -Infinity;
        }
        if (bName == '\xD8') {
            bScore = -Infinity;
        }
        
        if (aNum) {
            aScore -= ( 500 - aNum );
        }
        if (bNum) {
            bScore -= ( 500 - bNum );
        }
        if (!(aNum && bNum)) {
            aScore += aName.localeCompare(bName);  
        }
        return aScore - bScore;
    }

    /* 
    * Take the rows of the given table and give them "odd" and "even" 
    * classes
    */
    var reClassRows = function(table) {
        table.children('tr:odd').addClass('odd').removeClass('even');
        table.children('tr:even').addClass('even').removeClass('odd');
        table.children('tr').each( function() {
            if ($(this).data('isVisibleOnMap') == false) {
                $(this).addClass('notOnMap');
            } else {
                $(this).removeClass('notOnMap');
            }            
        });
    }

    var _self = {},
        _options = $.extend({
            // the table that will be sorted
            target: {},
            // the function to use for sorting. Takes two elements and 
            // returns a number: a negative number means the first given 
            // element comes before the second in the list, a positive 
            // number means the first element comes after the second, 
            // and a 0 means they're equal.
            sort: viewableSort,
            // optional callback when sorting is done
            callback: reClassRows
        }, options),
        // the given target as a table / jquery object
        _table;


    /* 
    * Set up the new viewable sorter
    */
    _self.init = function() {
        _table = $(_options.target);
        _self.sort = _options.sort;
        _self.callback = _options.callback;
        return _self;
    };

    /*
    * This method will remove all tr elements from the target table, sort 
    * them according to the given function, re-attach them to the table,
    * then call the callback method given in the initial options
    */
    _self.sortTable = function() {
        var elements = _table.children('tr');
        _table.detach('tr');
        elements.sort(_options.sort);
        elements.each( function() {
            _table.append(this);
        });
        _options.callback(_table);
    }

    return _self;
};

