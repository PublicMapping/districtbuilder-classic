reports = function(options) {

    var _self = {},
        _options = $.extend({
            previewContainer: $('#reportPreview'),
            trigger: $('#btnPreviewReport'),
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
    
    var $working = $('<div title="Working">Please wait while your report is created</div>').dialog({ 
        autoOpen: false,
        escapeOnClose: false,
        resizable:false,
        open: function(event, ui) { 
            $(".ui-dialog-titlebar-close", $(this).parent()).hide();
        }
    });

    var submitReportRequestToServer = function() {
        $working.dialog('open');
        data = getReportOptions();
        $.post(_options.reportUrl, data, loadPreviewContent);
    };

    var getReportOptions = function() {
        var getConcatenated = function(cls) {
            var value = '';
            $('.' + cls + '.reportVar').each( function() { 
                $this = $(this);
                if ($this.children('input:checked').length > 0) {
                    value += $this.children('label').text();
                    value += "|";
                    value += $this.children('input').val();
                    value += '^';
                }
            });
            if (value.length > 0) {
                return value.substring(0, value.length - 1);
            }
        };

        _popVar = $('#popVar').val();
        _popVarExtra = getConcatenated('popVarExtra');
        _partyControl = getConcatenated('partyControl');
        _racialComp = getConcatenated('racialComp');
        _splitVar = getConcatenated('splitVar');
        _repCompactness = $('#repCompactness').attr('checked');
        _repCompactnessExtra = $('#repCompactnessExtra').attr('checked');
        _repSpatial = $('#repSpatial').attr('checked');
        _repSpatialExtra = $('#repSpatialExtra').attr('checked');
        var data = { 
            popVar: _popVar,
            popVarExtra: _popVarExtra,
            racialComp: _racialComp,
            partyControl: _partyControl,
            splitVars: _splitVars,
            repCompactness: _repCompactness,
            repCompactnessExtra: _repCompactnessExtra,
            repSpatial: _repSpatial,
            repSpatialExtra: _repSpatialExtra
        };
        
        return data;
    };

    var loadPreviewContent = function(data, textStatus, XMLHttpRequest) {
        $working.dialog('close');
        if (data.success) {
            _options.previewContainer.html(data.preview); 
            var link = 'http://' + location.host + data.file
            $btnOpenReport = $('<a href="' + link + '" target="report" ><button id="btnOpenReport">Open report in a new window</button></a>');
            $('#reportButtons #btnOpenReport').remove();
            $('#reportButtons').append($btnOpenReport);  
            $('button', $btnOpenReport).button();
        } 
        else {
            $('<div title="Report Error">Sorry, we weren\'t able to preview this report; <p>' + data.message + '</p></div>').dialog({ autoOpen:true });
        }
    };

    return _self;
};
