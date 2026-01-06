(function(){
  function pad(n){return n<10?"0"+n:n}
  function updateClock(){
    var now=new Date();
    var h=pad(now.getHours());
    var m=pad(now.getMinutes());
    var days=['Söndag','Måndag','Tisdag','Onsdag','Torsdag','Fredag','Lördag'];
    var months=['januari','februari','mars','april','maj','juni','juli','augusti','september','oktober','november','december'];
    var dateStr=days[now.getDay()]+' '+now.getDate()+' '+months[now.getMonth()]+' '+now.getFullYear();
    var tEl=document.getElementById('sa-clock-time');
    var dEl=document.getElementById('sa-clock-date');
    if(tEl) tEl.textContent=h+':'+m;
    if(dEl) dEl.textContent=dateStr;
  }
  function applyTheme(){
    var root=document.querySelector('.sa-root');
    if(!root) return;
    var pref=localStorage.getItem('sa_theme')||'dark';
    root.classList.remove('sa-theme-light','sa-theme-dark');
    root.classList.add(pref==='dark'?'sa-theme-dark':'sa-theme-light');
  }
  function updateGreeting(){
    var header=document.querySelector('.sa-header');
    var el=document.getElementById('sa-greeting');
    if(!header||!el) return;
    var name=header.getAttribute('data-user-name')||'';
    var now=new Date();
    var h=now.getHours();
    var greet='God morgon';
    if(h>=11 && h<=16){greet='God middag'}
    else if(h>=17 || h<=4){greet='God kväll'}
    el.textContent=greet + (name?(', '+name):'') + ' 👋';
  }
  function updatePep(){
    var header=document.querySelector('.sa-header');
    var el=document.getElementById('sa-submessage');
    if(!header||!el) return;
    var name=header.getAttribute('data-user-name')||'';
    var h=(new Date()).getHours();
    var msgsMorning=[
      'Välkommen '+name+'.',
      'Idag blir det en bra dag, '+name+'!',
      'Nya möjligheter väntar, '+name+'.',
      'Let’s make it count, '+name+'.'
    ];
    var msgsNoon=[
      'Fortsätt starkt, '+name+'!',
      'Bra fart – håll i nu, '+name+'.',
      'Halfway there, '+name+'!',
      'Momentum är allt, '+name+'.'
    ];
    var msgsEve=[
      'Snyggt jobbat idag, '+name+'.',
      'En sak i taget, '+name+'.',
      'Another day, another dollar.',
      'Stabil insats, '+name+'.'
    ];
    var pool=msgsMorning;
    if(h>=11 && h<=16) pool=msgsNoon; else if(h>=17 || h<=4) pool=msgsEve;
    var pick=pool[Math.floor(Math.random()*pool.length)]||'';
    el.textContent=pick;
  }
  function toggleTheme(){
    var cur=localStorage.getItem('sa_theme')||'dark';
    var next=cur==='dark'?'light':'dark';
    localStorage.setItem('sa_theme',next);
    applyTheme();
  }
  document.addEventListener('DOMContentLoaded',function(){
    applyTheme();
    updateClock();
    updateGreeting();
    updatePep();
    setInterval(updateClock,60000);
    var btn=document.getElementById('sa-theme-toggle');
    if(btn) btn.addEventListener('click',toggleTheme);
  });
})();
