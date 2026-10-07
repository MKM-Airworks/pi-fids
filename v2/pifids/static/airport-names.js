const AirportNames={label(directory,code,language){
 const item=directory?.[String(code).trim().toUpperCase()];
 return item?.[language]||item?.en||code;
}};
if(typeof module!=='undefined')module.exports=AirportNames;
