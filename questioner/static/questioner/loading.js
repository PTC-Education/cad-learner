function loading_index() {
    var lists = document.getElementsByClassName("info_list"); 
    for (var i = 0; i < lists.length; i++) {
        lists[i].innerHTML = "<div class=\"loader\"></div>"; 
    }
}

function loading_modelling() {
    const main_content = document.getElementById("main"); 
    main_content.innerHTML = "<div class=\"loader\"></div>"; 
}