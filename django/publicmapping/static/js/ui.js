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
       This script file contains utility funtions that are used throughout
       the user interface for button and dialogs and tooltips.

   Author:
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

// comment out the following line to display the leaderboard wireframed components
//$(document).ready(function(){$('#tab_leaderboard').remove();$('#step_leaderboard').remove();$('#verifyandpost').remove();});

/**
 * Configure all buttons to look and behave like jQuery buttons.
 */
function loadButtons() {
    $('button, input[button]').button();
}

/**
 * Configure all tooltips. This function configures tags with the class
 * "divtip", "titletip", as well as the stats legend.
 */
function loadTooltips() {
    $(".divtip").tooltip({
        position: 'bottom left',
        offset: [8,10],
        delay: 200,
        predelay: 50,
        opacity: .8,
        onBeforeShow:  function() {
            // ensure proper DOM placement
            this.getTip().appendTo('body');
        },
        onHide:  function() {
            // restore original DOM placement
            this.getTip().appendTo(this.getTrigger());
        }
    });

    $(".titletip[title]").tooltip({
        position: 'bottom right',
        delay: 250,
        predelay: 600,
        opacity: .8
    });

    $('.evaluate .disabled').attr('title', gettext('Coming Soon...'));

    // If the user left the stats_legend_panel up when it's refreshed, it may be
    // attached to the body rather than appended to the trigger.
    $('body > #stats_legend_panel').remove();

    // This shows the legend when the trigger is clicked
    $("#stats_legend").tooltip({
        position: 'top center',
        effect: 'slide',
        delay: 200,
        offset: [10,0],
        opacity: .8,
        // Open this tip on click only, don't close it via tooltip methods
        events: {
            widget: 'click, none',
            tooltip: 'none'
        },
        onBeforeShow:  function() {
            // ensure proper DOM placement
            this.getTip().appendTo('body');
            // close on the next trigger click - putting this here as a "one()"
            // method keeps the handlers from piling up as the tabs are refreshed.
            var closeLegend = function() {
                var tip = $('#stats_legend').tooltip();
                if (tip.isShown(true)) {
                    tip.hide();
                }
                return false;
            };
            $('#stats_legend').one('click', closeLegend);
            $('.menu_toggle').one('click', closeLegend);
            $("#map_menu_header select").one('change', closeLegend);
        },
        onHide:  function() {
            // restore original DOM placement
            this.getTip().appendTo(this.getTrigger());
        }
    });
}

// Given a UTC time in ISO format, translate to browser local time
function getLocalTimeFromIsoformat(time) {
    var dashRE = new RegExp('\-','g');
    var milliRE = new RegExp('\.\\d*$');
    var tzRE = new RegExp('T');
    var date = new Date(time);
    if (isNaN(date)) {
        // additional text wrangling for IE
        time = time.replace(dashRE,'\/')
            .replace(milliRE,'')
            .replace(tzRE, ' ');
        date = new Date(time);
    }
    // Check whether timezone conversion is needed
    if ($.browser.mozilla) {
        // get the time zone offset in minutes, then multiply to get milliseconds
        var offset = date.getTimezoneOffset() * 60000;
        date = new Date(date - offset);
    }
    var hours = date.getHours();
    var minutes = date.getMinutes();

    // getMonth returns a value from 0-11, so we need to add 1
    var day = (date.getMonth() + 1) + "/" + date.getDate();
    return { hours: hours, minutes: minutes, day: day };
}


/**
 * Configure the tooltips, buttons, and leaderboard
 */
$(function() {
    var outstandingRequests = 0;
    var constructLeaderboardSection = function(container, owner) {
        $.ajax({
            type: 'GET',
            url: '/districtmapping/getleaderboard/',
            data: { owner_filter: owner, legislative_body: ($('#legSelectorLeaderboards').val() || 1) },
            success: function(html) {
                var panels = $('<div class="leaderboard_panels"></div>');
                container.append(panels);

                // insert the score panels HTML or a message stating that the
                // leaderboards are not yet filled
                if (html !== '') {
                    panels.html(html);
                } else {
                    panels.append($('<div id="no_leaderboards" />')
                        .text(gettext('No plans have been submitted for this leaderboard. Please check back later.')));
                }

                // check if we are no longer waiting for data
                outstandingRequests -= 1;
                if (outstandingRequests === 0) {
                    // create the tooltips
                    $(".leaderboard.divtip").tooltip({
                        position: 'bottom right',
                        offset: [8,10],
                        delay: 200,
                        predelay: 50,
                        opacity: .8,
                        onBeforeShow:  function() {
                            // ensure proper DOM placement
                            this.getTip().appendTo('body');
                        },
                        onHide:  function() {
                            // restore original DOM placement
                            this.getTip().appendTo(this.getTrigger());
                        }
                    });

                    // close the waiting dialog
                    $('#waiting').dialog('close');
                }
            },
            error: function(xhr, textStatus, message) {
                if (xhr.status == 403) {
                    window.location.href = '/?msg=logoff';
                }
            }
        });
    };

    // clears out any previous leaderboard elements, and constructs a new one
    var updateLeaderboard = function() {
        $("#topranked_content").remove();
        var toprankedDiv = $("#leaderboard_topranked").html('<div id="topranked_content"></div>');
        // construct the 'Top Ranked' section
        outstandingRequests += 1;
        constructLeaderboardSection(toprankedDiv, "all");

        var myRanked = $("#leaderboard_myranked")
        if (myRanked.length > 0) {
            $("#myranked_content").remove();
            var myrankedDiv = $("#leaderboard_myranked").html('<div id="myranked_content"></div>');
            outstandingRequests += 1;

            setTimeout( function(){
                constructLeaderboardSection(myrankedDiv, "mine");
            }, 500);
        }

        // show waiting dialog
        $('#waiting').dialog('open');
    };

    // connect the 'Verify and Submit Plan' button
    $('#btnVerifyAndSubmit').click(function() {
        $('#scoring').dialog({modal:true, resizable:false, autoOpen:true, escapeOnClose: false, open: function(event, ui) { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }});
        $.ajax({
            url: '/districtmapping/plan/' + PLAN_ID + '/score/',
            type: 'POST',
            success: function(data, textStatus, xhr) {
                $('#scoring').dialog('close');
                if (data.success) {
                    // score was successful, clear leaderboard
                    $("#topranked_content").remove();
                    $('#steps').tabs('select', '#step_leaderboard');
                } else {
                    // score failed, show reason
                    $('<div />').attr('title', gettext("Validation Failed")).html(data.message).dialog({autoOpen:true});
                }
            },
            error: function() {
                $('#scoring').dialog('close');
                $('<div />').attr('title', gettext('Error')).text(gettext('Server error. Please try again later')).dialog({autoOpen:true});
            }
        });
    });

    // create the update leaderboards button
    if ($('#txtPlanName').length > 0) {
        var button = $('<button class="leaderboard_button" />');
        button.html(gettext('Update Leaderboards<br/>with Working Plan'));
        button.button();
        $('#updateLeaderboardsContainer').append(button);

        // add handling for updating leaderboard with current plan
        button.click(function() {
            $('#waiting').dialog('open');
            $.ajax({
                url: '/districtmapping/plan/' + PLAN_ID + '/score/',
                type: 'POST',
                success: function(data, textStatus, xhr) {
                    $('#waiting').dialog('close');
                    if (data.success) {
                        // score was successful, show new results
                        updateLeaderboard();
                    } else {
                        // score failed, show reason
                        $('<div />').attr('title', gettext("Validation Failed"))
                            .html(data.message).dialog({autoOpen:true});
                    }
                },
                error: function() {
                    $('#waiting').dialog('close');

                    $('<div />').attr('title', gettext('Error'))
                        .text(gettext('Server error. Please try again later')).dialog({autoOpen:true});
                }
            });
        });
    }

    // create the leaderboard CSV download button
    var button = $('<button class="leaderboard_button" />').html(gettext('Download Scores<br/>as CSV')).button();
    $('#downloadLeaderboardsContainer').append(button);
    button.click(function() {
        var owner = $("#tab_myranked").hasClass("ui-state-active") ? "mine" : "all";
        window.location="/districtmapping/getleaderboardcsv/?owner_filter=" + owner +
            "&legislative_body=" + ($('#legSelectorLeaderboards').val() || 1);
    });

    // set the value of the legislative body dropdown
    if (window['BODY_ID']) {
        $('#legSelectorLeaderboards').val(BODY_ID);
    }

    // connect to legislative body changes
    $('#legSelectorLeaderboards').change( function() {
        updateLeaderboard();
    });

    // jQuery-UI tab layout
    $('#steps').tabs({
        select: function(e, ui) {
            $('#steps').trigger('tabSelected', [ui.index]);

            // lazy-load the leaderboard
            if ((ui.index === 4) && ($("#topranked_content").length === 0)) {
                updateLeaderboard();
            }
        }
    });

    // leaderboard tabs construction
    $('#leaderboard_tabs').tabs({
        // implement surrogate behavior as a workaround to new jQuery UI Tab design changes.
        select: function(e, ui) {
            if (ui.index == 0) {
                // Top ranked plans
                $('#leaderboard_myranked').hide();
                $('#leaderboard_topranked').show();
            } else {
                // My ranked plans
                $('#leaderboard_topranked').hide();
                $('#leaderboard_myranked').show();
            }
        }
    });
    // start myranked container as hidden
    $('#leaderboard_myranked').hide();

    $('#map_menu').tabs();
    $('#toolsets').tabs();

    // jQuery Tools tooltips
    loadTooltips();

    // jQuery-UI buttons
    loadButtons();


    // stats dropdown button
    $('.menu_toggle')
        .button({
            icons: {primary: 'ui-icon-arrow-down'}, text: false})
        .toggle(
            function(){
                $(this).button({icons: {primary: 'ui-icon-arrow-right'}, text: false})
            },
            function(){
                $(this).button({icons: {primary: 'ui-icon-arrow-down'}, text: false})
            })
        .click(function(){
            var show = $(".map_menu_content:visible'").length === 0;

            var sizeCB = function(show){
                $('#map_menu').css('bottom', show?'0':'auto');
            };

            if ( show ) {
                $('#map_settings_content, #legend_toggle').removeClass('collapse', 400);
                sizeCB(show);
                $storedPanel.slideDown(200);
            }
            else {
                $('.map_menu_content:visible').each(function() {
                    $storedPanel = $(this);
                    $storedPanel.slideUp(200,function(){sizeCB(show);});
                    $('#map_settings_content, #legend_toggle').addClass('collapse', 400);
                });
            }
        });


     //stats picker menu slider activation
     $('#map_menu_header select').change(function() {
         if ( $(".map_menu_content:visible'").length === 0) {
             $('#map_settings_content, #legend_toggle').removeClass('collapse', 400);
             $storedPanel.slideDown(200);
         }
     });

    // map editing buttons
    $('.toolset button, #history_tools button, #open_statistics_editor, #plan_export_container button')
        .button({
            icons: {primary: 'ui-icon'}
        })
        .click(function(){
            if($(this).hasClass('btntoggle')) {
                if(!$(this).hasClass('solotoggle')) {
                    $('.toolset_group button.btntoggle').removeClass('toggle');
                    $(this).addClass('toggle');
                }
            }
        });

    $('#saveplaninfo').bind('planSaved', function(event, time) {
        // there isn't a good, standard way to localize dates in javascript.
        // here, we need to show either dd/yy or yy/dd depending on the desired format.
        // as a simple workaround, inspect the date format set by the django localization
        // framework: if the first element is the date, set it first, else use the month.
        var local = getLocalTimeFromIsoformat(time),
            isDateFirst = DB.util.startsWith(get_format('SHORT_DATE_FORMAT'), 'd'),
            dateParts = local.day.split('/');

        var i18nParams = {
            day: isDateFirst ? (dateParts[1] + '/' + dateParts[0]) : (dateParts[0] + '/' + dateParts[1]),
            hour: (local.hours % 12) || 12,
            minute: ((local.minutes < 10) ? ('0' + local.minutes) : local.minutes)
        };

        $('#saveplaninfo').text(printFormat(gettext('Last Saved on %(day)s at %(hour)s:%(minute)s'), i18nParams));
    });


    try {
        var saved = $('#saveplaninfo').text().trim();
        $('#saveplaninfo').trigger('planSaved', [saved]);
    } catch (error) {
       // Just leave it: "no plan selected"
    }

    $('#map_legend').click(function(){
        var toggle = $(this);
        var panel = $('#map_legend_content');

        if(toggle.hasClass('active')) {
            toggle.removeClass('active');
            panel.slideUp(240);
        }
        else {
            toggle.addClass('active');
            panel.slideDown(240);
        }
    });
	
    var toggleMenu = function(targetId, menuDivId) {
        var target = $(targetId);
        var menuDiv = $(menuDivId);
        target.toggle(
            function() {
                menuDiv.slideDown(240);
            },
             function() {
                menuDiv.slideUp(240);
            }
        );
        menuDiv.slideUp(0);
    };

    toggleMenu('#plan_export_button', '#plan_export_menu');

    // Set up the language chooser
    toggleMenu('#language_menu_target', '#language_menu_div');
    $('.language_selection').click(function() {
        $('#language_form #language').val($(this).attr('id'));
        $('#language_form').submit();
    });

    $('#map_settings').click(function(){
        var toggle = $(this);
        var panel = $('#map_settings_content');

        if(toggle.hasClass('active')) {
            toggle.removeClass('active');
            panel.slideUp(240);
        }
        else {
            toggle.addClass('active');
            panel.slideDown(240);
        }
    });

    $('#map_type_settings').click(function(){
        var toggle = $(this);
        var panel = $('#map_type_content');

        if(toggle.hasClass('active')) {
            toggle.removeClass('active');
            panel.slideUp(240);
        }
        else {
            toggle.addClass('active');
            panel.slideDown(240);
        }
    });

    // report category parents toggling
    $('#reportdescription .master input').click( function() {
        $this = $(this);
        var id = $this.attr('id');
        var category = id.substring(0, id.indexOf('_'));
        var checked = $this.is(':checked');
        $('#reportdescription .' + category + ' input').prop('checked', $this.is(':checked'));
    });
    $('#reportdescription .reportVar input').click( function() {
        $this = $(this).closest('span');
        var id = $this.attr('id');
        var categories = $this.attr('class');
        var category = categories.split(' ')[0];
        if ($this.find('input').is(':checked') == false) {
            $('#' + category + '_master').prop('checked', false);
        }
    });

    /* The Save and Share button.  */
    $('#btnSaveAndShare').click( function() {
        // Helper function to get name for shared plan
        var getData = function() {
            var name = $('#txtPlanName').val().trim();
            if (name == '') { return false; }
            return { name: name, shared: true };
        };
        // The dialog to display while contacting the server.  Shouldn't be closable
        var $waitPublishing = $('<div />').attr('title', gettext('Please Wait')).text(gettext('Publishing with the server'));
        $waitPublishing.dialog({
            modal: true,
            autoOpen: true,
            escapeOnClose: false,
            resizable:false,
            open: function(event, ui) { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }
        });
        var data = getData();
        if (!data) {
            $waitPublishing.dialog('close');
            $('<div />').attr('title', gettext('Error')).text(gettext('Please enter a new name to publish your plan.')).dialog({ autoOpen: true });
            return false;
        }
        else {
            $.ajax({
                url: '/districtmapping/plan/' + PLAN_ID + '/copy/',
                type: 'POST',
                data: data,
                success: function(data, textStatus, xhr) {
                    $waitPublishing.dialog('close');
                    if (('success' in data) && !data.success) {
                        $waitPublishing.dialog('close');
                        $('<div />').attr('title', gettext('Oops!')).html(data.message).dialog({autoOpen:true});
                    }
                    else if (textStatus == 'success') {
                        var link = window.location.protocol + '//' + window.location.host + '/districtmapping/plan/' + data[0].pk + '/view/'
                        $('#sharedPermalink').html('<a href="' + link + '">' + link + '</a>');
                        // insert correct link for social network
                        //$('.twitter-tweet a').attr('data-url', link);
                        //$('.facebook-like fb\\:like, .google-plusone g\\:plusone' ).attr('href',link);
                        $('#continueEditing').click( function() {
                            $('#successfulShare').dialog('close');
                            $('#steps').tabs('select', '#step_draw');
                            $('#txtPlanName').val('');
                        });
                        if (typeof(_gaq) != 'undefined') { _gaq.push(['_trackEvent', 'Plans', 'Shared']); }
                        $('#successfulShare').dialog({autoOpen: true, width:460, resizable:false});
                    }
                },
                error: function() {
                    $waitPublishing.dialog('close');
                    $('<div />').attr('title', gettext('Server Failure')).text(gettext('Sorry, we weren\'t able to contact the server.  Please try again later.')).dialog({autoOpen:true});
                }
            });
        }
    });

    $('#agreelabel a').click( function() {
        $('#privacy').dialog('open');
    });

});

// When a plan is unloaded, allow the server to do any required cleanup
$(window).unload(function () {
    if (window['PLAN_ID']) {
        $.ajax({
            url: '/districtmapping/plan/' + PLAN_ID + '/unload/',
            type: 'POST',
            async: false
        });
    }
});
