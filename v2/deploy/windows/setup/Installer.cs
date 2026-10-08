using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Net;
using System.Net.Sockets;
[assembly: AssemblyTitle("Pi-FIDS Setup")]
[assembly: AssemblyVersion("2.0.0.0")]

class Installer : Form {
 ComboBox zone=new ComboBox(); RadioButton managerRole=new RadioButton(),displayRole=new RadioButton();int selectedRole=0;
 TextBox airport=new TextBox(),address=new TextBox(),connection=new TextBox();
 Label airportLabel=new Label(),zoneLabel=new Label(),addressLabel=new Label(),connectionLabel=new Label(),status=new Label();
 Button browse=new Button(),install=new Button();
 string payload;
 static string Quote(string value){return "\""+value.Replace("\"", "")+"\"";}
 [STAThread] static int Main(string[] args){
  Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
  if(args.Length>0 && args[0]=="/verify"){
   using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")){return stream!=null && stream.Length>100000?0:1;}
  }
  if(args.Length>1 && (args[0]=="/preview" || args[0]=="/preview-display")){
   using(var form=new Installer()){if(args[0]=="/preview-display")form.SetRole(1);form.Show();Application.DoEvents();using(var bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));bitmap.Save(args[1]);}form.Close();}return 0;
  }
  try{Application.Run(args.Length>0&&args[0]=="/register"?(Form)new Enrollment():new Installer());return 0;}catch(Exception ex){MessageBox.Show(ex.Message,"Pi-FIDS Setup");return 1;}
 }
 Installer(){
  Text="Pi-FIDS セットアップ";ClientSize=new Size(670,490);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;
  Font=new Font("Yu Gothic UI",10);
  var title=new Label(){Text="Pi-FIDS をこのPCにセットアップ",Location=new Point(28,22),Size=new Size(600,36),Font=new Font("Yu Gothic UI",16,FontStyle.Bold)};Controls.Add(title);
  var info=new Label(){Text="管理PC、または表示端末を選んでください。\n設置に使用するWindowsユーザーで実行してください。",Location=new Point(28,65),Size=new Size(610,48)};Controls.Add(info);
  AddLabel("このPCの役割",28,132);managerRole.Text="管理PC";managerRole.SetBounds(210,128,160,32);Controls.Add(managerRole);displayRole.Text="表示端末";displayRole.SetBounds(400,128,180,32);Controls.Add(displayRole);
  airportLabel=AddLabel("空港コード（3レター）",28,184);airport.SetBounds(210,180,180,32);airport.CharacterCasing=CharacterCasing.Upper;airport.MaxLength=3;Controls.Add(airport);
  zoneLabel=AddLabel("空港のタイムゾーン",28,236);zone.SetBounds(210,232,390,32);zone.Items.AddRange(new object[]{"Asia/Tokyo","Pacific/Palau","Asia/Bangkok","Asia/Singapore","Asia/Taipei","Asia/Seoul","Europe/London","America/New_York","Pacific/Honolulu","UTC"});zone.Text="Asia/Tokyo";Controls.Add(zone);
  addressLabel=AddLabel("管理PCのLANアドレス",28,288);address.SetBounds(210,284,390,32);Controls.Add(address);
  foreach(var ip in Dns.GetHostAddresses(Dns.GetHostName())){if(ip.AddressFamily==AddressFamily.InterNetwork && !IPAddress.IsLoopback(ip)){address.Text=ip.ToString();break;}}
  connectionLabel=AddLabel("端末専用の接続ファイル",28,184);connection.SetBounds(210,180,330,32);connection.ReadOnly=true;Controls.Add(connection);browse.Text="選択";browse.SetBounds(548,180,70,32);Controls.Add(browse);
  browse.Click+=(s,e)=>{using(var dialog=new OpenFileDialog(){Filter="接続設定 (*.json)|*.json",Title="管理PCで発行した接続ファイルを選択"}){if(dialog.ShowDialog()==DialogResult.OK)connection.Text=dialog.FileName;}};
  status.SetBounds(28,338,610,58);status.Text="ログイン時の自動起動・全画面表示・時刻同期を設定します。\n既存のPi-FIDSデータを上書きしません。";Controls.Add(status);
  install.Text="インストール";install.SetBounds(420,417,190,42);Controls.Add(install);
  var cancel=new Button(){Text="閉じる",Location=new Point(285,417),Size=new Size(120,42)};Controls.Add(cancel);cancel.Click+=(s,e)=>{if(install.Enabled)Close();};
  managerRole.CheckedChanged+=(s,e)=>{if(managerRole.Checked)SetRole(0);};displayRole.CheckedChanged+=(s,e)=>{if(displayRole.Checked)SetRole(1);};SetRole(0);
  install.Click+=async(s,e)=>{await RunInstall();};
 }
 void SetRole(int value){selectedRole=value;managerRole.Checked=value==0;displayRole.Checked=value==1;bool m=value==0;airport.Visible=airportLabel.Visible=zone.Visible=zoneLabel.Visible=address.Visible=addressLabel.Visible=m;connection.Visible=connectionLabel.Visible=browse.Visible=!m;}
 Label AddLabel(string text,int x,int y){var label=new Label(){Text=text,Location=new Point(x,y),Size=new Size(180,28)};Controls.Add(label);return label;}
 async Task RunInstall(){
  bool manager=selectedRole==0;
  if(manager && (airport.Text.Length!=3 || string.IsNullOrWhiteSpace(zone.Text)||string.IsNullOrWhiteSpace(address.Text))){MessageBox.Show("空港コード、タイムゾーン、LANアドレスを入力してください。");return;}
  if(!manager && !File.Exists(connection.Text)){MessageBox.Show("管理PCで発行した接続ファイルを選択してください。");return;}
  if(MessageBox.Show("このPCにPi-FIDSをセットアップします。続けますか？","Pi-FIDS",MessageBoxButtons.OKCancel)!=DialogResult.OK)return;
  install.Enabled=managerRole.Enabled=displayRole.Enabled=false;status.Text="セットアップ中です。しばらくお待ちください。";
  try{
   payload=Path.Combine(Path.GetTempPath(),"PiFidsSetup-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(payload);
   string zip=Path.Combine(payload,"payload.zip");using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))using(var output=File.Create(zip)){input.CopyTo(output);}
   await RunProcess("powershell.exe","-NoProfile -ExecutionPolicy Bypass -Command \"Expand-Archive -LiteralPath '"+zip.Replace("'","''")+"' -DestinationPath '"+Path.Combine(payload,"files").Replace("'","''")+"'\"",payload);
   string files=Path.Combine(payload,"files");
   string args="-NoProfile -ExecutionPolicy Bypass -File "+Quote(Path.Combine(files,manager?"Install-Manager.ps1":"Install-Display.ps1"));
   if(manager)args+=" -Airport "+Quote(airport.Text)+" -Timezone "+Quote(zone.Text)+" -LanAddress "+Quote(address.Text);
   else args+=" -ConnectionFile "+Quote(connection.Text);
   await RunProcess("powershell.exe",args,files);
   if(manager){
    string managerRoot=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MKM","PiFidsManager");
    File.Copy(Assembly.GetExecutingAssembly().Location,Path.Combine(managerRoot,"PiFidsSetup.exe"),true);
    string shortcutScript=Path.Combine(files,"Create-Enrollment-Shortcut.ps1");
    await RunProcess("powershell.exe","-NoProfile -ExecutionPolicy Bypass -File "+Quote(shortcutScript),files);
   }
   status.Text="セットアップが完了しました。\n再起動後、同じWindowsユーザーでログインして確認してください。";
   MessageBox.Show("セットアップが完了しました。","Pi-FIDS");
  }catch(Exception ex){status.Text="セットアップを完了できませんでした。";MessageBox.Show(ex.Message,"Pi-FIDS セットアップ結果");}
  finally{install.Enabled=managerRole.Enabled=displayRole.Enabled=true;if(payload!=null){try{Directory.Delete(payload,true);}catch{}}}
 }
 async Task RunProcess(string exe,string args,string directory){
  var start=new ProcessStartInfo(exe,args){WorkingDirectory=directory,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true};
  using(var process=Process.Start(start)){
   var output=process.StandardOutput.ReadToEndAsync();var error=process.StandardError.ReadToEndAsync();
   await Task.Run(()=>process.WaitForExit());string text=await output;string detail=await error;
   string log=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"MKM","PiFidsSetup.log");Directory.CreateDirectory(Path.GetDirectoryName(log));File.AppendAllText(log,DateTime.Now.ToString("s")+Environment.NewLine+text+detail+Environment.NewLine);
   if(process.ExitCode!=0)throw new Exception(detail.Length>0?detail:"処理に失敗しました。ログ: "+log);
  }
 }
}
