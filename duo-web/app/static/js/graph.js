(async function(){
  try{
    const data=await Duo.api('/api/graph');
    const container=document.getElementById('networkGraph');
    const groups={
      player:{shape:'dot',size:25,color:{background:'#5867ff',border:'#4050df'},font:{color:'#162033',size:12}},
      project:{shape:'diamond',size:22,color:{background:'#ed4db6',border:'#c83496'},font:{color:'#162033',size:10}},
      task:{shape:'dot',size:13,color:{background:'#13c8aa',border:'#09a98e'},font:{color:'#162033',size:9}},
      subject:{shape:'hexagon',size:17,color:{background:'#dbad34',border:'#b48819'},font:{color:'#162033',size:9}},
      activity:{shape:'star',size:17,color:{background:'#18a957',border:'#0e8745'},font:{color:'#162033',size:9}}
    };
    new vis.Network(container,{nodes:new vis.DataSet(data.nodes.map(n=>{const base={...n, ...groups[n.group]}; if(n.user_color){base.color={background:n.user_color,border:n.user_color};} return base;})),edges:new vis.DataSet(data.edges.map((e,i)=>({...e,id:i,arrows:'to',smooth:{type:'dynamic'},color:{color:'rgba(86,99,125,.42)'},font:{color:'#68738a',size:8}})))},{interaction:{hover:true,zoomView:true,dragView:true},physics:{enabled:true,stabilization:{iterations:170},barnesHut:{gravitationalConstant:-4200,springLength:125,springConstant:.035,damping:.16}},nodes:{borderWidth:1,font:{face:'Sora'}},edges:{width:1},layout:{improvedLayout:true}});
  }catch(e){Duo.toast(e.message);}
})();
