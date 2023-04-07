function loading_spin() {
    var lists = document.getElementsByClassName("info_list"); 
    for (var i = 0; i < lists.length; i++) {
        lists[i].innerHTML = "<div class=\"loader\"></div>"; 
    }
}