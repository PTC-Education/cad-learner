function search_filter() {
    // User input in the search menu 
    var input = document.getElementById("searchInput"); 
    var filter = input.value.toUpperCase(); 

    // Get difficulty level  selected 
    var q_level; 
    if (document.getElementById("easy_q").checked) {
        q_level = "Difficulty: Easy"; 
    } else if (document.getElementById("med_q").checked) {
        q_level = "Difficulty: Medium"; 
    } else if (document.getElementById("hard_q").checked) {
        q_level = "Difficulty: Challenging"; 
    } else {
        q_level = "all"; 
    }
    
    // Get question type selected 
    var q_type; 
    if (document.getElementById("single_type").checked) {
        q_type = "Challenge type: Single-part Part Studio"; 
    } else if (document.getElementById("multi_type").checked) {
        q_type = "Challenge type: Multi-part Part Studio"; 
    } else if (document.getElementById("assem_type").checked) {
        q_type = "Challenge type: Assembly Mating"; 
    } else if (document.getElementById("multi_step").checked) {
        q_type = "(Multi-Step)"; 
    } else {
        q_type = "all"; 
    }
    //document.getElementById("disclaimer").innerHTML = q_type.substring(0,27)
    // Get availability if reviewer 
    var is_reviewer = document.getElementById("is_reviewer").value === "True"; 
    var q_avail; 
    if (is_reviewer){
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

    // filter the questions
    for (var i = 0; i < questions.length; i++) {
        var level = questions[i].getElementsByClassName("difficulty")[0].innerHTML; 
        var type = questions[i].getElementsByClassName("q_type")[0].innerHTML;
        var q_name = questions[i].getElementsByClassName("accordion")[0].getElementsByClassName("challenge_title")[0]; 
        if (is_reviewer) {
            var avail = (
                q_avail === "all" || 
                q_avail === questions[i].getElementsByClassName("availability")[0].innerHTML
            ); 
        } else {
            var avail = true; 
        }
        if (q_type=="(Multi-Step)") {
            if ( (q_level === "all" || q_level === level) && (type.slice(-12) == q_type) && avail && q_name.innerHTML.toUpperCase().indexOf(filter) > -1) {
                questions[i].style.display = ""; 
            }
            else {
                questions[i].style.display = "none"; 
            }
        }
        else if (
                (q_level === "all" || q_level === level) && (q_type === "all" || q_type.substring(0,27) === type.substring(0,27)) && avail && 
                q_name.innerHTML.toUpperCase().indexOf(filter) > -1
            ) {
            questions[i].style.display = ""; 
        } else {
            questions[i].style.display = "none"; 
        }
    }
}