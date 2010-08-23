reports = function(options) {

    var _self = {},
        _options = $.extend({
            previewContainer: $('#reportPreview'),
            trigger: $('#btnViewReport'),
            reportUrl: '',
            callback: function() {}
        }, options),
        _popVar,
        _popVarExtra,
        _ratioVars,
        _splitVars,
        _blockLabelVar,
        _repCompactness,
        _repCompactnessExtra,
        _repSpatial,
        _repSpatialExtra;

    _self.init = function() {
        _options.trigger.click( function() {
            submitReportRequestToServer();
            _options.callback(); 
        });
        return _self;
    };
    
    var submitReportRequestToServer = function() {
        data = getReportOptions();
        $.post(_options.reportUrl, data, loadPreviewContent);
    };

    var getReportOptions = function() {
        var getConcatenated = function(class) {
            var value = '';
            $('.' + class + '.reportVar').each( function() { 
                $this = $(this);
                if ($this.children('input:checked').length > 0) {
                    value += $this.children('label').text();
                    value += "|";
                    value += $this.children('input').val();
                    value += '^';
                }
            });
            return value.substring(0, value.length - 1);
        };

        _popVar = $('#popVar').val();
        _popVarExtra = getConcatenated('popVarExtra');
        _partyControl = getConcatenated('partyControl');
        _racialComp = getConcatenated('racialComp');
        _splitVar = getConcatenated('splitVar');
        _repCompactness = $('#repCompactness input').attr('checked');
        _repCompactnessExtra = $('#repCompactnessExtra input').attr('checked');
        _repSpatial = $('#repSpatial input').attr('checked');
        _repSpatialExtra = $('#repSpatialExtra input').attr('checked');
        var data = { 
            popVar: _popVar,
            popVarExtra: _popVarExtra,
            racialComp: _racialComp,
            partyControl: _partyControl,
            splitVars: _splitVars,
            repCompactness: _repCompactness,
            repCompactnessExtra: _repCompactnessExtra,
            prepSpatial: _repSpatial,
            repSpatialExtra: _repSpatialExtra
        };
        
        return data;
    };

    var loadPreviewContent = function(data, textStatus, XMLHttpRequest) {
        if (data.success) {
            _options.previewContainer.html(data.preview); 
        } 
        else {
            $('<div title="Report Error>Sorry, we weren\'t able to preview this report; <p>' + data.message + '</p></div>').dialog({ autoOpen:true });
        }
    };

    return _self;
};
