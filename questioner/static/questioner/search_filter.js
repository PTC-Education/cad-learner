function search_filter() {
    // User input in the search menu 
    var input = document.getElementById("searchInput"); 
    var filter = input.value.toUpperCase(); 

    // Get difficulty level is selected 
    var q_type; 
    if (document.getElementById("easy_q").checked) {
        q_type = "Difficulty: Easy"; 
    } else if (document.getElementById("med_q").checked) {
        q_type = "Difficulty: Medium"; 
    } else if (document.getElementById("hard_q").checked) {
        q_type = "Difficulty: Challenging"; 
    } else {
        q_type = "all"; 
    }
    
    // Get availability if reviewer 
    var q_avail; 
    if (document.getElementById("is_reviewer").value === "True"){
        if (document.getElementById("rev_pub").checked){
            q_avail = "Availability: Published"; 
        } else if (document.getElementById("rev_unpub").checked){
            q_avail = "Availability: Unpublished"; 
        }
        else {
            q_avail = "all"; 
        }
    } else {
        q_avail = "all"; 
    }

    // Get all the questions that are published 
    var questions = document.getElementsByClassName("question"); 

    for (var i = 0; i < questions.length; i++) {
        var level = questions[i].getElementsByClassName("difficulty")[0].innerHTML; 
        var avail = questions[i].getElementsByClassName("availability")[0].innerHTML; 
        var q_name = questions[i].getElementsByClassName("accordion")[0].getElementsByTagName("h3")[0]; 
        if ((q_type === "all" || q_type === level) && (q_avail === "all" || q_avail === avail) && q_name.innerHTML.toUpperCase().indexOf(filter) > -1) {
            questions[i].style.display = ""; 
        } else {
            questions[i].style.display = "none"; 
        }
    }
}