
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
        aName = a.children('.celldistrictname').text();
        bName = b.children('.celldistrictname').text();
        aNum = parseInt(aName);
        bNum = parseInt(bName);

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

