using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
class Enrollment : Form {
 TextBox name=new TextBox(),id=new TextBox();ComboBox usage=new ComboBox(),profile=new ComboBox();Label status=new Label();Button save=new Button();string root,airport;
 public Enrollment(){
  root=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MKM","PiFidsManager");
  if(!File.Exists(Path.Combine(root,"data","site.json")))throw new Exception("先に管理PCをインストールしてください。");
  var json=new JavaScriptSerializer();var site=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(root,"data","site.json")));airport=(string)site["airport"];
  Text="Pi-FIDS 表示端末を追加";ClientSize=new Size(650,410);Font=new Font("Yu Gothic UI",10);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
  LabelText("表示端末を追加（"+airport+"）",26,20,580,36);
  LabelText("端末名",26,85,160,28);name.SetBounds(190,80,410,32);Controls.Add(name);
  LabelText("端末ID",26,137,160,28);id.SetBounds(190,132,410,32);Controls.Add(id);
  LabelText("用途",26,189,160,28);usage.SetBounds(190,184,410,32);usage.DropDownStyle=ComboBoxStyle.DropDownList;usage.Items.AddRange(new object[]{"出発便一覧","到着便一覧","チェックイン・ゲート画像"});Controls.Add(usage);
  LabelText("表示する画像",26,241,160,28);profile.SetBounds(190,236,410,32);profile.DropDownStyle=ComboBoxStyle.DropDownList;Controls.Add(profile);
  using(var web=new WebClient()){web.Encoding=Encoding.UTF8;var registry=json.Deserialize<Dictionary<string,object>>(web.DownloadString("http://127.0.0.1:8800/api/registry?airport="+airport));foreach(Dictionary<string,object> item in (IEnumerable)registry["profiles"])profile.Items.Add((string)item["name"]);}
  usage.SelectedIndexChanged+=(s,e)=>profile.Enabled=usage.SelectedIndex==2;usage.SelectedIndex=0;if(profile.Items.Count>0)profile.SelectedIndex=0;
  status.SetBounds(26,285,590,48);status.Text="端末IDは重複しない英数字を指定してください（例：gate-02）。";Controls.Add(status);
  save.Text="登録して接続ファイルを発行";save.SetBounds(300,347,300,40);Controls.Add(save);
  save.Click+=async(s,e)=>{await Register();};
 }
 void LabelText(string text,int x,int y,int w,int h){Controls.Add(new Label(){Text=text,Location=new Point(x,y),Size=new Size(w,h)});}
 string Q(string value){return "\""+value.Replace("\"", "")+"\"";}
 async Task Register(){
  if(string.IsNullOrWhiteSpace(name.Text)||!System.Text.RegularExpressions.Regex.IsMatch(id.Text,"^[A-Za-z0-9_-]{1,40}$")){MessageBox.Show("端末名と正しい端末IDを入力してください。");return;}
  if(usage.SelectedIndex==2&&profile.SelectedItem==null){MessageBox.Show("管理画面で表示画像を先に登録してください。");return;}
  save.Enabled=false;
  try{
   string[] choices={"departure","arrival","signage"};
   string args="-NoProfile -ExecutionPolicy Bypass -File "+Q(Path.Combine(root,"Prepare-Display.ps1"))+" -Root "+Q(root)+" -Airport "+Q(airport)+" -DisplayId "+Q(id.Text)+" -TerminalName "+Q(name.Text)+" -Usage "+choices[usage.SelectedIndex];
   if(usage.SelectedIndex==2)args+=" -ProfileName "+Q((string)profile.SelectedItem);
   var start=new ProcessStartInfo("powershell.exe",args){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
   using(var process=Process.Start(start)){var output=process.StandardOutput.ReadToEndAsync();var error=process.StandardError.ReadToEndAsync();await Task.Run(()=>process.WaitForExit());await output;string detail=await error;if(process.ExitCode!=0)throw new Exception(detail);}
   string file=Path.Combine(root,"data","enrollment",id.Text+".connection.json");status.Text="登録しました。接続ファイルを対象の表示端末に渡してください。";MessageBox.Show("接続ファイル：\n"+file,"Pi-FIDS");Process.Start("explorer.exe", "/select,"+Q(file));
  }catch(Exception ex){MessageBox.Show(ex.Message,"端末登録結果");}finally{save.Enabled=true;}
 }
}
