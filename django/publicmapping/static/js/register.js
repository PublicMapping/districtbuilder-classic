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
       This script file defines the behaviors and components used for
       the user registration and login process.

   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Define an anonymous function to be called when the document is ready.
 */
$(function(){
    var dOptions = {
        autoOpen:false,
        width:475,
        dialogClass:'register-dialog',
        modal:true,
        resizable: false
    };
    // configure the registration dialog
    $('#register').dialog(dOptions);
    $('#privacy').dialog($.extend({title:gettext('Terms of Use'), height: 375},dOptions));
    $('#forgotpass').dialog($.extend({title:gettext('Forgot Password')},dOptions));
    $('#sessiondupe').dialog($.extend({title:gettext('Duplicate Session')},dOptions));
    $('#sessionsmax').dialog($.extend({title:gettext('Maximum Users Exceeded')},dOptions));

    // generic dialog in case registration is unavailable
    var genericRegistrationError = function() {
        $('#register').dialog('close');
        $('#doRegister').attr('disabled',true).css('cursor', 'not-allowed');
        $('#sign_up').attr('disabled',true).css('cursor', 'not-allowed');
        $('<div class="error">').text(gettext("Sorry, registration is not available at this time.  Please try logging in anonymously or coming back later")).dialog({
            modal: true,
            title: gettext("Signup Unavailable"),
            resizable:false, 
            width:300
        });
    };

    // when the register form is submitted, do some client side validation
    // first, before sending it up to the server
    $('#doRegister').click(function(evt) {
        var frm = $('#registerForm'),
            username = frm.find('#newusername'),
            newpasswordfield1 = frm.find('#newpassword1'),
            newpasswordfield2 = frm.find('#newpassword2'),
            newpassword1 = '',
            newpassword2 = '',
            passwordhint = frm.find('#passwordhint'),
            email = frm.find('#email'),
            agree = frm.find('#agree'),
            userid = frm.find('#userid');

        var validateUsername = function(name) {
            if ($.trim(name) === '' ||
                    // No beginning or trailing spaces.
                    name.indexOf(' ') == 0 ||
                    name.lastIndexOf(' ') == name.length - 1 ||
                    name.length < 6 || name.length > 30 ||
                    !name.match(/.*[A-Za-z]+.*/)) {
                return false;
            }
            return true;
        };

        if (!validateUsername(username.val())) {
            username.removeClass('field');
            username.addClass('error');
            return false;
        }
        else {
            username.removeClass('error');
            username.addClass('field');
        }

        if (newpasswordfield1.val() != newpasswordfield2.val()) {
            newpasswordfield1.removeClass('field');
            newpasswordfield1.addClass('error');
            newpasswordfield2.removeClass('field');
            newpasswordfield2.addClass('error');
            return false;
        }
        else {
            newpasswordfield1.removeClass('error');
            newpasswordfield1.addClass('field');
            newpasswordfield2.removeClass('error');
            newpasswordfield2.addClass('field');
        }

        if ( username.attr('disabled') == null || newpasswordfield1.val() != '') {
            // A basic password complexity test; At least 8 characters and at least
            // one number, one lower-case letter and one upper-case letter
            var isComplex = function(password) {
                return /\d/.test(password) &&
                     /[a-z]/.test(password) &&
                     /[A-Z]/.test(password) &&
                     password.length >= 8;
            };

            if (!isComplex(newpasswordfield1.val())) {
                $('#passwordinstructions').css('color', 'red');
                return false;
            }
            else {
                $('#passwordinstructions').css('color', '');
            }
            newpassword1 = Sha1.hash(newpasswordfield1.val());
            newpassword2 = Sha1.hash(newpasswordfield2.val());
        }

        if (passwordhint.val() == '') {
            passwordhint.removeClass('field');
            passwordhint.addClass('error');
            return false;
        }
        else {
            passwordhint.addClass('field');
            passwordhint.removeClass('error');
        }
        if ($.trim(email.val()) != '') {
            if (!(email.val().match(/^([\w\-\.\+])+\@([\w\-\.])+\.([A-Za-z]{2,4})$/))) {
                email.removeClass('field');
                email.addClass('error');
                return false;
            }
            else {
                email.addClass('field');
                email.removeClass('error');
            }            
        }

        if (agree.length > 0 && !agree[0].checked) {
            $('#agreerow').addClass('required');
            return false;
        }

        jQuery.ajax({
            context:frm[0],
            data: { 
                userid:$('#userid').val(),
                newusername:username.val(),
                newpassword1:newpassword1,
                newpassword2:newpassword2,
                email:email.val(),
                passwordhint:passwordhint.val(),
                firstname:$('#firstname').val(),
                lastname:$('#lastname').val(),
                organization:$('#organization').val(),
                csrfmiddlewaretoken:$('input[name=csrfmiddlewaretoken]').val()
            },
            dataType:'json',
            type:'POST',
            url:frm[0].action,
            success:function(data,textStatus,xhr){
                if ($('#userid').val() == '') {
                    $('#dupemail').css('display','none');
                    if (data.success) {
                        if (typeof(_gaq) != 'undefined') { _gaq.push(['_trackEvent', 'Users', 'Registered']); }
                        $('#register').dialog('close');
                        $('<div />').text(gettext("You've been registered for the public mapping project.")).dialog({
                            modal:true,
                            width:300,
                            title:gettext("Success!"),
                            buttons: [{
                                text: gettext("Start Mapping"),
                                click: function() {
                                    window.location.href = data.redirect;
                                    return; }}],
                            resizable:false,
                            open: function(event, ui) {
                                $(".ui-dialog-titlebar-close", $(this).parent()).hide();
                            }
                        });
                    } else if (data.message == 'name exists') {
                        var newusername = $('#newusername');
                        newusername.removeClass('field');
                        newusername.addClass('error');
                        $('<div />').text(gettext("User Name already exists. Please choose another one.")).dialog({
                            modal: true, autoOpen: true, title: gettext('Error'), resizable:false
                        });                
                    } else if (data.message == 'email exists') {
                        var email = $('#email');
                        email.removeClass('field');
                        email.addClass('error');
                        $('#dupemail').css('display','block');
                        $('<div />').text(gettext("Email already exists. Enter another one, or use the password retrieval form")).dialog({
                            modal: true, autoOpen: true, title: gettext('Error'), resizable:false
                        });                
                    } else {
                        genericRegistrationError();
                    }
                }
                else {
                    if (data.success) {
                        newpasswordfield1.val('');
                        newpasswordfield2.val('');
                    }
                    $('#register').dialog('close');
                }
            },
            error:function(xhr,textStatus,error){
                genericRegistrationError();
            }
        });

        return false;
    });

    // go straight to the viewing pg
    $('#doAnonymous').click(function(evt) {
        window.location.href = '/accounts/logout/?next=/districtmapping/plan/0/view/';
        return false;
    });

    // when the remind button is clicked, display a dialog for options
    // available for password recovery.
    $('#doRemind').click(function(evt){
        var frm = $('#forgotForm')[0];
        $('#forgotusername, #forgotemail').removeClass('error');

        var remindBtn = $('#doRemind');
        remindBtn.attr('disabled',true);
        var btnText = remindBtn.text();
        remindBtn.html('<span class="ui-button-text" />').text(gettext('Please Wait...'));

        $.ajax({
            context:frm,
            data: {
                username: $('#forgotusername').val(),
                email: $('#forgotemail').val(),
                csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val()
            },
            dataType:'json',
            type:'POST',
            url:frm.action,
            success: function(data,textStatus,xhr){
                var remindBtn = $('#doRemind');
                remindBtn.attr('disabled',null);
                remindBtn.html('<span class="ui-button-text">'+btnText+'</span>');
                if (data.success) {

                    if (data.mode == 'hinting') {
                        $('#forgotprompt, #forgotButton').css('display','none');
                        $('#forgothint, #forgotButton2').css('display','block');
                        $('#forgothintbox').val( data.hint );
                    }
                    else if (data.mode == 'sending') {
                        $('#forgotprompt, #forgotButton').css('display','none');
                        $('#forgotsent, #forgotButton2').css('display','block');
                    }
                }
                else if (data.field) {
                    if (data.field != 'email') {
                        $('#forgotusername').addClass('error');
                    }
                    if (data.field != 'username') {
                        $('#forgotemail').addClass('error');
                    }
                }
            },
            error:function(xhr,textStatus,error){
                var remindBtn = $('#doRemind');
                remindBtn.html('<span class="ui-button-text">'+btnText+'</span>');
                remindBtn.attr('disabled',true);
            },
            complete:function(xhr, textStatus){
                $('#forgotusername').val('');
                $('#forgotemail').val('');
            }
        });

        return false;
    });

    // do this operation when a user goes 'back' in the dialog
    $('#doBack').click(function(){
        $('#forgotprompt, #forgotButton').css('display','block');
        $('#forgothint, #forgotsent, #forgotButton2').css('display','none');
        return false;
    });

    // do this operation when a user closes the dialog
    $('#doClose').click(function(){
        $('#forgotpass').dialog('close');
        $('#forgotprompt, #forgotButton').css('display','block');
        $('#forgothint, #forgotsent, #forgotButton2').css('display','none');
        return false;
    });

    // if the location of this page has /account/login/ in it, it must have
    // been the result of a failed login redirect. display error notices
    // around the username and password fields
    if (new RegExp('.*/accounts/login/$').test(window.location.href)) {
        $('<div class="error" />').text(gettext('You entered an incorrect user name or password')).dialog({
            modal:true,
            width:300,
            resizable:false,
            title:gettext('Login Error')
        });
        $('#username, #passphrase').addClass('error');
    } else if( 'opensessions' in window && opensessions > 1 ) {
        // If there is a page variable named opensessions, and it is
        // greater than one, that means that we've been bumped back to
        // the index page after attempting a login. This means that the
        // user attempting to log in has an active session on another
        // browser or computer. Give them options on how to access the app.
        $('#sessiondupe').dialog('open');
        $('#force_close').click(function() {
            var frm = $('#purge_form')[0];
            $.ajax({
                context:frm,
                data: {
                    username: $('#purge_username').val()
                },
                dataType:'json',
                type:'POST',
                url:frm.action,
                success: function(data,textStatus,xhr){
                    $('#sessiondupe').dialog('close');
                },
                error: function(xhr,textStatus,error) {
                    $('#sessiondupe').dialog('close');
                }
            });
            return false;
        });
        $('#different_login').click(function() {
            $('#sessiondupe').dialog('close');
            return false;
        });
    } else if ( 'availsession' in window && !availsession ) {
        // If there is a page variable named availsession, and it is
        // false, that means that we've been bumped back to the index
        // page after attempting a login. This means that the maximum
        // number of active sessions has been reached. Inform the user
        // to come back and try again later.
        $('#sessionsmax').dialog('open');
    } else {
        var re = new RegExp('[\\?\\&].+?=[^\\&]*','g');
        var matches = window.location.search.match(re);
        for (var i = 0; matches !== null && i < matches.length; i++) {
            var re2 = new RegExp('[\\?\\&](.+?)=([^\\&]*)$');
            var matches2 = matches[i].match(re2);

            if (matches2[1] == 'msg' && matches2[2] == 'logoff') {
                var dialog = $('<div id="logoffdlg" />');
                dialog.attr('title', gettext('Logged Off'));
                dialog.append($('<p />').text(gettext("You have been logged off by another browser. This happens sometimes if you attempt to access the application from two different locations.")));
                dialog.append($('<h1 />').text(gettext('Please log in again')));
                dialog.dialog({
                    modal:true,
                    resizable:false
                });
                return;
            }
        }
    }

});
