$(function() {
		$('#steps').tabs();
    
    $("button").button();
    
    $(".menu_toggle")
        .button({
          icons: {primary: 'ui-icon-triangle-1-s'},text: false})
        .toggle(
          function(){
            $(this).button({icons: {primary: 'ui-icon-triangle-1-e'}})
          },
          function(){
            $(this).button({icons: {primary: 'ui-icon-triangle-1-s'}})
          })
        .click(function(){
          $('.map_menu_content').slideToggle(200);
        });

    $('.toolbar_toggle').click(function(){
        $currtoolset = $(this).parent();
        $currtoolset.hide();
        $('.toolset').not($currtoolset).show()
    })
    $("button").button();

    $('.toolbar_toggle').click(function(){
        $currtoolset = $(this).parent();
        $currtoolset.hide();
        $('.toolset').not($currtoolset).show()
    })
    
    
	});
