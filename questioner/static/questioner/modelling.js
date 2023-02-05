function confirm_alert() {
    return confirm("Warning, your modeling time will be reset and you will need to restart the challenge. To return to the home page click OK.");
}

const root = document.documentElement;
 
document.addEventListener('mousemove', evt => {
    let x = evt.clientX / innerWidth;
    let y = evt.clientY / innerHeight;
 
    root.style.setProperty('--mouse-x', x);
    root.style.setProperty('--mouse-y', y);
});