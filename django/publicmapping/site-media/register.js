$(function(){
    var dOptions = {
        autoOpen:false,
        width:425,
        modal:true,
        resizable: false
    };
    // configure the registration dialog
    $('#register').dialog($.extend({title:'Register'},dOptions));
    $('#forgotpass').dialog($.extend({title:'Forgot Password'},dOptions));

    // when the register form is submitted, do some client side validation
    // first, before sending it up to the server
    $('#doRegister').click(function(evt) {
        var frm = $('#registerForm'),
            username = frm.find('#newusername'),
            newpassword1 = frm.find('#newpassword1'),
            newpassword2 = frm.find('#newpassword2'),
            passwordhint = frm.find('#passwordhint'),
            agree = frm.find('#agree');

        if (username.val() == '' || username.val().length > 30) {
            username.removeClass('field');
            username.addClass('error');
            return false;
        }
        else {
            username.removeClass('error');
            username.addClass('field');
        }

        if (newpassword1.val() == '' ||
            newpassword1.val() != newpassword2.val()) {
            newpassword1.removeClass('field');
            newpassword1.addClass('error');
            newpassword2.removeClass('field');
            newpassword2.addClass('error');
            return false;
        }
        else {
            newpassword1.removeClass('error');
            newpassword1.addClass('field');
            newpassword2.removeClass('error');
            newpassword2.addClass('field');
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

        if (!agree[0].checked) {
            $('#agreelabel').addClass('required');
            return false;
        }
        
        jQuery.ajax({
            context:frm[0],
            data: { 
                newusername:$('#newusername').val(),
                newpassword1:$('#newpassword1').val(),
                newpassword2:$('#newpassword2').val(),
                email:$('#email').val(),
                passwordhint:$('#passwordhint').val(),
                firstname:$('#firstname').val(),
                lastname:$('#lastname').val(),
                organization:$('#organization').val()
            },
            dataType:'json',
            type:'POST',
            url:frm[0].action,
            success:function(data,textStatus,xhr){
                if (data.success) {
                    window.location.href = data.redirect;
                    return;
                }

                var newusername = $('#newusername');
                newusername.removeClass('field');
                newusername.addClass('error');
            },
            error:function(xhr,textStatus,error){
                $('#doRegister').attr('disabled',true);
            }
        });

        return false;
    });

    // when the anonymous button is clicked, fake a login as the
    // 'anonymous' user, a special user
    $('#doAnonymous').click(function(evt) {
        var frm = $('#anonymousForm')[0];
        $.ajax({
            context:frm,
            data: {
                newusername:'anonymous',
                newpassword1:'anonymous',
                email:''
            },
            dataType:'json',
            type:'POST',
            url:frm.action,
            success:function(data,textStatus,xhr){
                if (data.success) {
                    window.location.href = data.redirect;
                    return;
                }
            },
            error:function(xhr,textStatus,error){
                $('#doAnonymous').attr('disabled',true);
            }
        });

        return false;
    });

    $('#doRemind').click(function(evt){
        var frm = $('#forgotForm')[0];
        $('#forgotusername, #forgotemail').removeClass('error');

        $.ajax({
            context:frm,
            data: {
                username: $('#forgotusername').val(),
                email: $('#forgotemail').val()
            },
            dataType:'json',
            type:'POST',
            url:frm.action,
            success: function(data,textStatus,xhr){
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
                $('#doRemind').attr('disabled',true);
            }
        });

        return false;
    });

    $('#doBack').click(function(){
        $('#forgotprompt, #forgotButton').css('display','block');
        $('#forgothint, #forgotsent, #forgotButton2').css('display','none');
        return false;
    });

    $('#doClose').click(function(){
        $('#forgotpass').dialog('close');
        $('#forgotprompt, #forgotButton').css('display','block');
        $('#forgothint, #forgotsent, #forgotButton2').css('display','none');
        return false;
    });

    if (new RegExp('.*/accounts/login/$').test(window.location.href)) {
        $('#username, #password').addClass('error');
    }
});
