var formfield = document.getElementById('url_field_form');

function add(){
  var newField = document.createElement('input');
  newField.setAttribute('type','text');
  newField.setAttribute('name','ref_url');
  newField.setAttribute('class','text');
  newField.setAttribute('size',50);
  newField.setAttribute('placeholder','Onshape URL...');
  formfield.appendChild(newField);
}

function remove(){
  var input_tags = formfield.getElementsByTagName('input');
  if(input_tags.length > 1) {
    formfield.removeChild(input_tags[(input_tags.length) - 1]);
  }
}