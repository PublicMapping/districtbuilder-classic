$(function() {
		$('#steps').tabs();
    
    $('#mapmenuheader').click(function(){
        $('#mapmenucontent').slideToggle(200);
    })
    $("button").button();

    $('.toolbar_toggle').click(function(){
        $currtoolset = $(this).parent();
        $currtoolset.hide();
        $('.toolset').not($currtoolset).show()
    })
    
    
	});
