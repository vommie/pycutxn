; Buttons zum schnellen vor und zurückschalten der geöffneten Dateien

; Kategorien-Label leeren, wenn keine Kategorien gesetzt wurden

; Wenn Auto-Save aus ist, dann auch VDub-Save-Modus deaktivieren
; Konzept überdenken. Momentan wird wenn Auto-Save aktiviert ist, ein gewählter Eintrag überschrieben, wenn man mit VDub speichert.

#include "shared.au3"

Global $ini_section = 'xnview'
Global $xnview_db_path = False
Global $xnview_db_tagtree_array
Global $icon_default = 'xnview_tagger.ico'

; Globals
Global $input_file_path = False
Global $input_file_split_array = False
Global $combo_file_array = False
Global $combo_history_size = False
Global $selected_tagids_array = False
Global $rating = 0
Global $filter_array = False
Global $vdub_save_mode_string = 'VDub-Save-Modus'

; States
$auto_load = True
$auto_save = True
$vdub_save_mode = False

; GUI
Global $gui_xnview_listview
Global $gui_xnview_combo_filename
Global $gui_xnview_label_selected_categories_text
Global $platzhalter

; Gestalterische Änderungen des ListViews
Global $font_bold = _WinAPI_CreateFont(14, 5, 0, 0, 700)
Global $font_normal = _WinAPI_CreateFont(14, 5, 0, 0, 400)

Init()

Func Init()
	_Icon($icon_default)
	If Not _FirstScriptInstanceCheck() Then
		MsgBox(64,$script_xnview_title,'Es läuft bereits eine Instanz')
		Exit
	EndIf
	_LogCreate() ; Logdatei erstellen
	_Log('---', 'INITIALISIERE')

	; Datenbank ermitteln
	$xnview_db_path = _Ini(1, $ini_section, "xnview_db_path", -1, "error")
	If $xnview_db_path = "error" Or Not FileExists($xnview_db_path) Then
		$xnview_db_path = FileOpenDialog('XnView-Pfad auswählen', @ProgramFilesDir, 'Datenbank (*.db)', 1, 'XnView.db')
		If @error = 1 Then
			_Log('Error: XnView-Datenbank nicht angegeben. Beende.', 1)
			Exit
		Else
			_Log('XnView-Datenbank wurde eingetragen: "' & $xnview_db_path & '"', 1)
			_Ini(2, $ini_section, 'xnview_db_path', $xnview_db_path)
		EndIf
	Else
		_Log("Datenbank: " & $xnview_db_path, 1)
	EndIf
	; Combo-Box vorbereiten
	$combo_history_size = _Ini(1, $ini_section, "history_size", -1, 10)
	If Not ComboCreateFromIni() Then
		_Log('Fehler bei Combo-Box-Erstellung. Beende',1)
		Exit
	EndIf
	; Auto-Settings
	$auto_load = _Ini(1,$ini_section,'auto_load',-1,1) = 1
	$auto_save = _Ini(1,$ini_section,'auto_save',-1,1) = 1
	; Filterliste für Listview-Kategorien
	$filter_array = _Ini(1,$ini_section,'filterlist',-1,False)
	If $filter_array Then
		$filter_array = StringSplit($filter_array,'|',2)
		If @error Then
			$filter_array = False
			_Log('Error: Kann Filterliste nicht spliten',1)
		Else
			_Log(UBound($filter_array) & ' Filter gefunden',1)
		EndIf
	Else
		_Log('Keine Filter gesetzt')
	EndIf
	Main()
EndFunc   ;==>Init

Func Main()
	_Log('---', 'MAIN')

	; Kategorien auslesen
	If Not DB_GetCategoriesCount() Then Return (False)
	If Not DB_GetCategoriesTree() Then Return (False)
	; $xnview_db_tagtree_array[0]-[3]: [0] Tag Label, [1] TagID, [2] SubID, [3] Listview-Index
	_ArraySort($xnview_db_tagtree_array, 0, 0, 0, 0) ; Array nach Namen der Kategorien sortieren

	; Kommunikations-Form
	$gui_msg_form = GUICreate($script_xnview_title_msg,0,0,0,0)

	; Form
	$gui_xnview_form_x = _Ini(1, $ini_section, 'form_x', -1, '4')
	$gui_xnview_form_y = _Ini(1, $ini_section, 'form_y', -1, '100')
	$gui_xnview_form_w = _Ini(1, $ini_section, 'form_w', -1, '338')
	$gui_xnview_form_h = _Ini(1, $ini_section, 'form_h', -1, '500')
	$gui_xnview_form = GUICreate($script_xnview_title, $gui_xnview_form_w, $gui_xnview_form_h, $gui_xnview_form_x, $gui_xnview_form_y, $WS_SIZEBOX, BitOR($WS_EX_ACCEPTFILES,$WS_EX_TOOLWINDOW))
	; Dateiname-Leiste
	Opt("GUIResizeMode", $GUI_DOCKLEFT + $GUI_DOCKTOP + $GUI_DOCKHEIGHT + $GUI_DOCKRIGHT)
	$gui_xnview_combo_filename = GUICtrlCreateCombo('', 1, 0, $gui_xnview_form_w - 4, default, BitOR($CBS_DROPDOWN,$CBS_AUTOHSCROLL,$CBS_DROPDOWNLIST,$CBS_OEMCONVERT))
	; Bewertungsleiste
	Opt("GUIResizeMode", $GUI_DOCKALL)
	$pos_parent = ControlGetPos($gui_xnview_form, '', $gui_xnview_combo_filename)
	$top = $pos_parent[1] + $pos_parent[3] + 1
	$hgt = 14
	$gui_xnview_label_rating_0_frame = GUICtrlCreateLabel('', 0, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_0_bg = GUICtrlCreateLabel('', 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, 0xdddddd)
	$gui_xnview_label_rating_0_text = GUICtrlCreateLabel('0', 0, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_1_frame = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 1, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_1_bg = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 1 + 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_1_text = GUICtrlCreateLabel('1', $gui_xnview_form_w / 6 * 1, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_2_frame = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 2, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_2_bg = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 2 + 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_2_text = GUICtrlCreateLabel('2', $gui_xnview_form_w / 6 * 2, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_3_frame = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 3, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_3_bg = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 3 + 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_3_text = GUICtrlCreateLabel('3', $gui_xnview_form_w / 6 * 3, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_4_frame = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 4, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_4_bg = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 4 + 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_4_text = GUICtrlCreateLabel('4', $gui_xnview_form_w / 6 * 4, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_5_frame = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 5, $top, $gui_xnview_form_w / 6, $hgt, $SS_ETCHEDFRAME)
	Global $gui_xnview_label_rating_5_bg = GUICtrlCreateLabel('', $gui_xnview_form_w / 6 * 5 + 1, $top + 1, $gui_xnview_form_w / 6 - 3, $hgt - 3)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	$gui_xnview_label_rating_5_text = GUICtrlCreateLabel('5', $gui_xnview_form_w / 6 * 5, $top, $gui_xnview_form_w / 6, $hgt, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	; Listview
	Opt("GUIResizeMode", $GUI_DOCKLEFT + $GUI_DOCKTOP + $GUI_DOCKBOTTOM + $GUI_DOCKRIGHT)
	$top = $top + $hgt
	$gui_xnview_listview = GUICtrlCreateListView('|||', 0, $top, $gui_xnview_form_w - 2, $gui_xnview_form_h - 92, $LVS_LIST, BitOR($WS_EX_CLIENTEDGE, $LVS_EX_CHECKBOXES))
	GUICtrlSetState($gui_xnview_listview,$GUI_DROPACCEPTED)
	_GUICtrlListView_AddColumn(GUICtrlGetHandle($gui_xnview_listview), 'label', 200)
	_GUICtrlListView_AddColumn(GUICtrlGetHandle($gui_xnview_listview), 'tagid', 60)
	_GUICtrlListView_AddColumn(GUICtrlGetHandle($gui_xnview_listview), 'subid', 60)
	; Listview Kontextmenü
	$gui_xnview_menu_listview = GUICtrlCreateContextMenu($gui_xnview_listview)
	$gui_xnview_menu_listview_reset = GUICtrlCreateMenuItem('Meta-Infos zurücksetzen', $gui_xnview_menu_listview)
	; Ausgewählte Kategorien
	Opt("GUIResizeMode", $GUI_DOCKLEFT + $GUI_DOCKBOTTOM + $GUI_DOCKHEIGHT + $GUI_DOCKRIGHT)
	$pos_parent = ControlGetPos($gui_xnview_form, '', $gui_xnview_listview)
	$gui_xnview_label_selected_categories_bg = GUICtrlCreateLabel('', $pos_parent[0], $pos_parent[1] + $pos_parent[3] + 2, $gui_xnview_form_w - 4, 17, $SS_ETCHEDFRAME)
	GUICtrlSetTip($gui_xnview_label_selected_categories_bg,'Linksklick: Kategorien zuvor gespeicherter Datei markieren')
	$gui_xnview_label_selected_categories_frame = GUICtrlCreateLabel('', $pos_parent[0] + 1, $pos_parent[1] + $pos_parent[3] + 3, $gui_xnview_form_w - 7, 14, $SS_WHITERECT)
	$gui_xnview_label_selected_categories_text = GUICtrlCreateLabel('', $pos_parent[0], $pos_parent[1] + $pos_parent[3] + 3, $gui_xnview_form_w - 4, 17, $SS_CENTER)
	GUICtrlSetBkColor(-1, $GUI_BKCOLOR_TRANSPARENT)
	; Buttonleiste
	Opt("GUIResizeMode", $GUI_DOCKLEFT + $GUI_DOCKBOTTOM + $GUI_DOCKHEIGHT + $GUI_DOCKWIDTH)
	$pos_parent = ControlGetPos($gui_xnview_form, '', $gui_xnview_label_selected_categories_frame)
	$gui_xnview_button_opt = GUICtrlCreateButton('Opt...', 2, $pos_parent[1] + $pos_parent[3] + 2, 40, 17)
	$gui_xnview_button_log = GUICtrlCreateButton('Log', 44, $pos_parent[1] + $pos_parent[3] + 2, 40, 17)
	Opt("GUIResizeMode", $GUI_DOCKRIGHT + $GUI_DOCKBOTTOM + $GUI_DOCKHEIGHT + $GUI_DOCKWIDTH)
	$gui_xnview_button_load = GUICtrlCreateButton('Laden', $gui_xnview_form_w - 62 - 46, $pos_parent[1] + $pos_parent[3] + 2, 44, 17)
	$gui_xnview_button_save = GUICtrlCreateButton('Speichern', $gui_xnview_form_w - 62, $pos_parent[1] + $pos_parent[3] + 2, 60, 17)
	; Opt-Button-Kontextmenü
	$gui_xnview_dummy_menu_opt = GUICtrlCreateDummy()
	$gui_xnview_menu_opt = GUICtrlCreateContextMenu($gui_xnview_dummy_menu_opt)
	$gui_xnview_menu_opt_autoload = GUICtrlCreateMenuItem('Auto-Load', $gui_xnview_menu_opt)
	GUICtrlSetState($gui_xnview_menu_opt_autoload, $GUI_UNCHECKED)
	$gui_xnview_menu_opt_autosave = GUICtrlCreateMenuItem('Auto-Save', $gui_xnview_menu_opt)
	GUICtrlSetState($gui_xnview_menu_opt_autosave, $GUI_UNCHECKED)
	GUICtrlCreateMenuItem('', $gui_xnview_menu_opt)
	$gui_xnview_menu_opt_history = GUICtrlCreateMenuItem('Verlauf-Einträge: ' & $combo_history_size, $gui_xnview_menu_opt)


	; Zusatz
	_GUICtrlListView_BeginUpdate(GUICtrlGetHandle($gui_xnview_listview))
	ListViewCreateCategoriesTree(-1) ; Kategorien-Baum erstellen, mit Hauptkategorien (SubID = -1) beginnen
	_GUICtrlListView_EndUpdate(GUICtrlGetHandle($gui_xnview_listview))
	ComboUpdate() ; ComboBox füllen
	If $auto_load = 1 Then GUICtrlSetState($gui_xnview_menu_opt_autoload, $GUI_CHECKED)
	If $auto_save = 1 Then GUICtrlSetState($gui_xnview_menu_opt_autosave, $GUI_CHECKED)

	GUIRegisterMsg($WM_NOTIFY, "WM_NOTIFY")
	GUIRegisterMsg($WM_NOTIFY, "WM_NOTIFY")

	GUISetState(@SW_SHOW)

	$timer_msg = 1000000
	While 1

		If TimerDiff($timer_msg) > 500 Then
			$title_msg = WinGetTitle($gui_msg_form)
			If StringInStr($title_msg,'{XnView:Save}') Then
				_Log('---','NACHRICHT')
				_Log('Titel-Nachricht empfangen: Save')
				$title_msg_array = StringSplit($title_msg,'|')
				If @error Then
					_Log('Error: Kann Titel-Nachricht nicht splitten',1)
				Else
					If $title_msg_array[0] > 1 Then
						OpenInVDubMode($title_msg_array[2])
					EndIf
				EndIf
			WinSetTitle($title_msg,'',$script_xnview_title_msg)
			EndIf
			$timer_msg = TimerInit()
		EndIf

		$nMsg = GUIGetMsg()
		Switch $nMsg
			Case $GUI_EVENT_CLOSE
				Quit($gui_xnview_form)
			Case $GUI_EVENT_DROPPED ; Wenn Datei gedroppt wurde, diese öffnen
				Open(@GUI_DRAGFILE)
			Case $gui_xnview_combo_filename
				$index = _GUICtrlComboBox_GetCurSel(GUICtrlGetHandle($gui_xnview_combo_filename))
				If $index = -1 Then
					_Log('Error: Kann gewählten ComboBox-Eintrag nicht auslesen',1)
				Else
					If UBound($combo_file_array)-1 < $index Then
						_Log($vdub_save_mode_string & ' aktiv. Lesevorgang abgebrochen.',1)
					Else
						Open($combo_file_array[$index])
					EndIf
				EndIf
			Case $gui_xnview_label_rating_0_frame
				GuiSetRating(0)
			Case $gui_xnview_label_rating_1_frame
				GuiSetRating(1)
			Case $gui_xnview_label_rating_2_frame
				GuiSetRating(2)
			Case $gui_xnview_label_rating_3_frame
				GuiSetRating(3)
			Case $gui_xnview_label_rating_4_frame
				GuiSetRating(4)
			Case $gui_xnview_label_rating_5_frame
				GuiSetRating(5)
			Case $gui_xnview_menu_listview_reset
				Reset()
			Case $gui_xnview_label_selected_categories_bg
				If IsArray($selected_tagids_array) Then
					; TagID-Array klonen, aber ohne den 0. Key der die Anzahl der Keys angibt, weil das die aufgerufene Funktion nicht braucht
					Local $selected_tagids_temp_array[$selected_tagids_array[0]]
					For $c = 1 To $selected_tagids_array[0]
						$selected_tagids_temp_array[$c-1] = $selected_tagids_array[$c]
					Next
					ListViewSelectCategories($selected_tagids_temp_array)
				EndIf
			Case $gui_xnview_button_opt
				ShowMenu($gui_xnview_form, $nMsg, $gui_xnview_menu_opt)
			Case $gui_xnview_menu_opt_autoload
				_Log('Benutzereingabe...')
				If BitAND(GUICtrlRead($gui_xnview_menu_opt_autoload), $GUI_CHECKED) = $GUI_CHECKED Then
					GUICtrlSetState($gui_xnview_menu_opt_autoload, $GUI_UNCHECKED)
					_Ini(2,$ini_section,'auto_load',0)
					$auto_load = False
					_Log('Auto-Load deaktiviert',1)
				Else
					GUICtrlSetState($gui_xnview_menu_opt_autoload, $GUI_CHECKED)
					_Ini(2,$ini_section,'auto_load',1)
					$auto_load = True
					_Log('Auto-Load aktiviert',1)
				EndIf
			Case $gui_xnview_menu_opt_autosave
				_Log('Benutzereingabe...')
				If BitAND(GUICtrlRead($gui_xnview_menu_opt_autosave), $GUI_CHECKED) = $GUI_CHECKED Then
					GUICtrlSetState($gui_xnview_menu_opt_autosave, $GUI_UNCHECKED)
					_Ini(2,$ini_section,'auto_save',0)
					$auto_save = False
					_Log('Auto-Save deaktiviert',1)
				Else
					GUICtrlSetState($gui_xnview_menu_opt_autosave, $GUI_CHECKED)
					_Ini(2,$ini_section,'auto_save',1)
					$auto_save = True
					_Log('Auto-Save aktiviert',1)
				EndIf
			Case $gui_xnview_menu_opt_history
				_Log('Benutzereingabe...')
				$input = InputBox('Verlauf-Einträge','Anzahl von Einträgen im Verlauf',$combo_history_size,'',200,90)
				$input = Int($input)
				If IsInt($input) And $input > 0 Then
					$combo_history_size = $input
					_Ini(2,$ini_section,'history_size',$combo_history_size)
					GUICtrlSetData($gui_xnview_menu_opt_history,'Verlauf-Einträge: ' & $combo_history_size)
					_Log('Anzahl von Verlauf-Einträgen geändert auf ' & $combo_history_size,1)
				Else
					_Log('Error: Fehlerhafte Benutzereingabe bei Änderung der Verlaufs-Einträge',1)
				EndIf
			Case $gui_xnview_button_log
				If Not WinExists($logview_title) Then ShellExecute($script_logview_path, $log_file, @ScriptDir)
			Case $gui_xnview_button_save
				Save(0)
			Case $gui_xnview_button_load
				Load(0)
		EndSwitch
	WEnd
EndFunc   ;==>Main

Func GuiSetRating($newrating)
	_Log('Ändere Bewertung...')
	If $newrating > 5 Then
		_Log('Error: Rating darf nicht über 5 sein',1)
		Return(False)
	EndIf

	$rating = $newrating
	If $newrating <> 0 Then GUICtrlSetBkColor($gui_xnview_label_rating_0_bg, $GUI_BKCOLOR_TRANSPARENT)
	If $newrating <> 1 Then GUICtrlSetBkColor($gui_xnview_label_rating_1_bg, $GUI_BKCOLOR_TRANSPARENT)
	If $newrating <> 2 Then GUICtrlSetBkColor($gui_xnview_label_rating_2_bg, $GUI_BKCOLOR_TRANSPARENT)
	If $newrating <> 3 Then GUICtrlSetBkColor($gui_xnview_label_rating_3_bg, $GUI_BKCOLOR_TRANSPARENT)
	If $newrating <> 4 Then GUICtrlSetBkColor($gui_xnview_label_rating_4_bg, $GUI_BKCOLOR_TRANSPARENT)
	If $newrating <> 5 Then GUICtrlSetBkColor($gui_xnview_label_rating_5_bg, $GUI_BKCOLOR_TRANSPARENT)
	Switch $newrating
		Case 0
			GUICtrlSetBkColor($gui_xnview_label_rating_0_bg, 0xdddddd)
		Case 1
			GUICtrlSetBkColor($gui_xnview_label_rating_1_bg, 0xeeaaaa)
		Case 2
			GUICtrlSetBkColor($gui_xnview_label_rating_2_bg, 0xffcc88)
		Case 3
			GUICtrlSetBkColor($gui_xnview_label_rating_3_bg, 0x88ee88)
		Case 4
			GUICtrlSetBkColor($gui_xnview_label_rating_4_bg, 0x6688ee)
		Case 5
			GUICtrlSetBkColor($gui_xnview_label_rating_5_bg, 0xcc88ee)
	EndSwitch
	_Log('Bewertung geändert auf: ' & $rating,1)
	Return(True)
EndFunc   ;==>GuiSetRatingTrans

Func GuiSetCategoriesLabel()
	If Not IsArray($selected_tagids_array) Or Not IsArray($xnview_db_tagtree_array) Then
		GUICtrlSetData($gui_xnview_label_selected_categories_text,'')
		Return(False)
	EndIf
	Local $last_categories_string = False
	For $c = 1 To $selected_tagids_array[0]
		For $c_label = 0 To UBound($xnview_db_tagtree_array)-1
			If $xnview_db_tagtree_array[$c_label][1] = $selected_tagids_array[$c] Then
				If Not $last_categories_string Then
					$last_categories_string = $xnview_db_tagtree_array[$c_label][0]
				Else
					$last_categories_string &= ', ' & $xnview_db_tagtree_array[$c_label][0]
				EndIf
			EndIf
		Next
	Next
	GUICtrlSetData($gui_xnview_label_selected_categories_text,$last_categories_string)
	Return(True)
EndFunc

Func Open($file) ; Bei Drag&Drop oder ComboBox-Auswahl
	; VDub-Save-Modus deaktivieren
	$vdub_save_mode = False
	$index = _GUICtrlComboBox_FindString(GUICtrlGetHandle($gui_xnview_combo_filename),$vdub_save_mode_string)
	If $index > 0 Then _GUICtrlComboBox_DeleteString(GUICtrlGetHandle($gui_xnview_combo_filename),$index)

	; Meta-Infos aktueller Datei speichern
	If $auto_save Then
		If $input_file_path Then Save(1)
	EndIf

	_Log('---','ÖFFNEN')
	_Log('Öffne Datei...: "' & $file & '"')
	; Meta-Infos resetten
	Reset()
	; Neue Datei zur aktuellen machen
	$input_file_path = $file
	; Langen Dateinamen splitten
	If _Get_FileSplitArray($input_file_path) Then
		If ComboUpdate() Then
			If $auto_load Then Load()
		EndIf
	Else
		$input_file_path = False
		$input_file_split_array = False
	EndIf
EndFunc

Func OpenInVDubMode($file) ; Bei Save von VDub
	$vdub_save_mode = True
	$input_file_path = $file
	If _Get_FileSplitArray($input_file_path) Then
		$index = _GUICtrlComboBox_FindString(GUICtrlGetHandle($gui_xnview_combo_filename),$vdub_save_mode_string)
		If $index > 0 Then _GUICtrlComboBox_DeleteString(GUICtrlGetHandle($gui_xnview_combo_filename),$index)
		If ComboUpdate() Then
			Save(1)
			GuiSetCategoriesLabel()
			Reset()
			$index = _GUICtrlComboBox_AddString(GUICtrlGetHandle($gui_xnview_combo_filename),$vdub_save_mode_string)
			_GUICtrlComboBox_SetCurSel(GUICtrlGetHandle($gui_xnview_combo_filename),$index)
			$input_file_path = False
			$input_file_split_array = False
		EndIf
	Else
		$input_file_path = False
		$input_file_split_array = False
	EndIf
EndFunc

Func Load($log_auto = 1)
	_Log('---', 'LADEN')
	If $log_auto = 1 Then
		_Log('Automatisches Laden...')
	Else
		_Log('Manuelles Laden...')
	EndIf

	; Schauen, ob für aktuelle Datei ein Datenbankeintrag existiert - wenn ja, auslesen und in ListView eintragen
	$folder_id = DB_GetFolderID()
	If Not $folder_id Then
		_Log('Abbruch - keine FolderID gefunden. Es existiert kein Eintrag.',1)
		Return(False)
	EndIf
	$image_id = DB_GetImageID($folder_id)
	If Not $image_id Then
		_Log('Abbruch - keine ImageID gefunden. Es existiert kein Eintrag.',1)
		Return(False)
	EndIf
	DB_GetRatingForFile($image_id)
	If Not $rating Then
		_Log('Abbruch - Fehler beim auslesen des Ratings.',1)
		Return(False)
	Else
		GuiSetRating($rating)
	EndIf
	$xnview_db_file_tags_array = DB_GetCategoriesForFile($image_id)
	If Not IsArray($xnview_db_file_tags_array) Then
		_Log('Abbruch - Keine Kategorien ausgelesen.',1)
		Return(False)
	EndIf
	If Not ListViewSelectCategories($xnview_db_file_tags_array) Then
		_Log('Abbruch - Fehler beim markieren der Kategorien im ListView.',1)
		Return(False)
	Else
		_Log('Erfolg. Kategorien gefunden und im Listview markiert.',1)
		Return(True)
	EndIf
EndFunc

Func Save($log_auto = 1)
	_Log('---', 'SPEICHERN')
	If $log_auto = 1 Then
		_Log('Automatische Speicherung...: "' & $input_file_path & '"')
	Else
		_Log('Manuelle Speicherung...: "' & $input_file_path & '"')
	EndIf
	If Not $input_file_path Then
		_Log('Error: Es fehlen Variablen.',1)
		Return(False)
	EndIf

	; Selektierte Kategorien aus ListView auslesen.
	If Not ListViewGetCategories() Then ; Wenn keine Kategorien gewählt, schauen ob wenigstens Rating gesetzt ist
		If $rating = 0 Then
			_Log('Kein User-Rating entdeckt. Meta-Infos werden zurückgesetzt.', 1)
		Else
			_Log('User-Rating entdeckt. Fahre mit Speicherung fort.', 1)
		EndIf
	EndIf

	; FolderID ermitteln oder ggf. neu erstellen
	$folder_id = DB_GetFolderID() ; Ermittle FolderID
	If Not $folder_id Then $folder_id = DB_CreateFolderID() ; Wenn FolderID noch nicht besteht, dann erstelle FolderID
	If Not $folder_id Then ; Wenn FolderID nicht erstellt werden konnte, dann breche ab
		_Log('Abbruch! Fehler beim ermitteln und erstellen einer FolderID', 1)
		Return (False)
	EndIf

	; ImageID ermitteln oder ggf. neu erstellen
	$image_id = DB_GetImageID($folder_id) ; Ermittle ImageID
	If Not $image_id Then ; Neue ImageID eintragen
		$image_id = DB_CreateImageID($folder_id) ; Neuen ImageID-Eintrag erstellen
		If Not $image_id Then
			_Log('Abbruch! Fehler beim ermitteln und erstellen einer ImageID', 1)
			Return (False)
		EndIf
	EndIf

	; ImageID mit neuen Meta-Infos (Kategorien, Bewertung) updaten
	If Not DB_SetRating($folder_id, $image_id) Then Return (False)
	If Not DB_DeleteCategories($image_id) Then Return (False)
	If IsArray($selected_tagids_array) Then
		If Not DB_SetCategories($image_id) Then Return (False)
	EndIf

	Return (True)
EndFunc   ;==>Save

Func Reset()
	_Log('Resette Meta-Infos...')
	GuiSetRating(0)
	ListViewClearCategories()
	_Log('Fertig.',1)
EndFunc

Func ComboCreateFromIni()
	; Array in der Größe der History-Size anlegen
	Global $combo_file_array[$combo_history_size]

	; Array aus Ini füllen
	For $c = 0 To $combo_history_size-1
		$combo_file_array[$c] = _Ini(1, $ini_section, "history_" & $c, -1, False)
	Next
	Return(True)
EndFunc

Func ComboSaveToIni()
	For $c = 0 To UBound($combo_file_array)-1
		If $combo_file_array[$c] Then
			_Ini(2,$ini_section,'history_' & $c,$combo_file_array[$c])
		Else
			_Ini(2,$ini_section,'history_' & $c,'')
		EndIf
	Next
EndFunc

Func ComboUpdate()
	_Log('Update Datei-History...')

	If $input_file_path Then ; Wenn neue Datei geöffnet wird, dann schauen ob bereits vorhanden, sonst Array anpassen
		For $c = 0 To UBound($combo_file_array)-1
			If $combo_file_array[$c] = $input_file_path Then ; Wenn aktuelle Datei bereits in History vorhanden ist...
				_Log('Eintrag in History gefunden. Rufe diesen auf.',1)
				_GUICtrlComboBox_SetCurSel(GUICtrlGetHandle($gui_xnview_combo_filename),$c) ; Selektiere diesen Eintrag
				Return(True)
			EndIf
		Next

		; Aktuelle Datei am Anfang eintragen, ältesten Eintrag rauswerfen
		_Log('Erstelle neuen History-Eintrag.',1)
		_ArrayPush($combo_file_array,$input_file_path,1)
		ComboSaveToIni()
	EndIf

	; Alle Einträge entfernen
	If $combo_file_array[0] Then ; Wenn es überhaupt einen Eintrag gibt (ini), dann ComboBox neu aufbauen
		_GUICtrlComboBox_BeginUpdate(GUICtrlGetHandle($gui_xnview_combo_filename))
		$count = _GUICtrlComboBox_GetCount(GUICtrlGetHandle($gui_xnview_combo_filename))
		If $count <> 0 Then
			For $c = 0 To UBound($combo_file_array)-1
				If Not $combo_file_array[$c] Then ExitLoop
				_GUICtrlComboBox_DeleteString(GUICtrlGetHandle($gui_xnview_combo_filename),0)
			Next
		EndIf
		; Einträge neu einpflegen
		For $c = 0 To UBound($combo_file_array)-1
			If Not $combo_file_array[$c] Then ExitLoop
			$check = _GUICtrlComboBox_AddString(GUICtrlGetHandle($gui_xnview_combo_filename),$combo_file_array[$c])
		Next
		_GUICtrlComboBox_EndUpdate(GUICtrlGetHandle($gui_xnview_combo_filename))
		_Log('ComboBox erfolgreich geupdated.',1)
	Else
		_Log('Keine Einträge vorhanden, womit ComboBox gefüllt werden könnte.',1)
	EndIf

	If Not $vdub_save_mode Then
		If $input_file_path Then _GUICtrlComboBox_SetCurSel(GUICtrlGetHandle($gui_xnview_combo_filename),0)
	EndIf

	Return(True)
EndFunc

Func ListViewCreateCategoriesTree($current_tagid) ; Funktion ruft sich selbst auf, bis keine weitere SubID-Verweisung gefunden wird
	Local $prefix, $suffix, $skip = False

	If $current_tagid <> -1 Then ; Wenn nicht TagID = -1, also keine Hauptkategorie, dann
		$platzhalter &= '  ' ; Leerzeichen vor der Schleife, die neue Subitems erstellt, hinzufügen
	EndIf

	; Schleife so lange wiederholen, bis keine SubID mehr auf eine TagID verweist (also keine weitere Unterkategorie mehr existiert)
	For $c = 0 To UBound($xnview_db_tagtree_array) - 1
		If $xnview_db_tagtree_array[$c][2] = $current_tagid Then ; Wenn SubID auf aktuelle TagID verweist, dann hinzufügen
			; Filter
			If IsArray($filter_array) Then ; Wenn Filter gesetzt sind...
				For $c_filter = 0 To UBound($filter_array)-1 ; Aktuelle TagID mit Filtern vergleichen
					If $xnview_db_tagtree_array[$c][0] = $filter_array[$c_filter] Then ; Wenn Treffer, dann skippen
						$skip = True
						ExitLoop
					Else
						$skip = False
					EndIf
				Next
			EndIf
			If $skip = False Then
				$index = _GUICtrlListView_AddItem(GUICtrlGetHandle($gui_xnview_listview), $platzhalter & $xnview_db_tagtree_array[$c][0])
				_GUICtrlListView_AddSubItem(GUICtrlGetHandle($gui_xnview_listview), $index, $xnview_db_tagtree_array[$c][1], 1)
				_GUICtrlListView_AddSubItem(GUICtrlGetHandle($gui_xnview_listview), $index, $xnview_db_tagtree_array[$c][2], 2)
				ListViewCreateCategoriesTree($xnview_db_tagtree_array[$c][1])
			EndIf
		EndIf
	Next
	$platzhalter = StringTrimRight($platzhalter, 2) ; Leerzeichen wieder kürzen, wenn Subitem-Schleife beendet ist
EndFunc   ;==>ListViewCreateCategoriesTree

Func ListViewGetCategories()
	_Log('ListView - Ermittle ausgewählte Kategorien...')

	; Einträge mit gesetztem Haken suchen und auflisten
	Local $selected_tagids = False
	$count = _GUICtrlListView_GetItemCount(GUICtrlGetHandle($gui_xnview_listview))
	For $c = 0 To $count - 1
		$check = _GUICtrlListView_GetItemChecked(GUICtrlGetHandle($gui_xnview_listview), $c)
		If $check Then
			$index = _GUICtrlListView_GetItemText(GUICtrlGetHandle($gui_xnview_listview), $c, 1)
			If $index Then
				If $selected_tagids Then
					$selected_tagids &= ', ' & $index
				Else
					$selected_tagids = $index
				EndIf
			EndIf
		EndIf
	Next

	; Wenn keine Einträge selektiert sind, abbrechen
	If Not $selected_tagids Then
		_Log('Keine markierten Einträge gefunden.', 1)
		$selected_tagids_array = False
		Return (False)
	EndIf

	; Gefundene markierte Einträge in Array splitten
	If StringInStr($selected_tagids, ', ') Then
		$selected_tagids_array = StringSplit($selected_tagids, ', ', 1)
		If @error Then
			_Log('Error: Kann markierte Einträge nicht splitten', 1)
			Return (False)
		Else
			_Log($selected_tagids_array[0] & ' markierte Einträge ermittelt: ' & $selected_tagids, 1)
		EndIf
	Else ; Wenn nur ein Eintrag gewählt, Array erstellen
		Global $selected_tagids_array[2]
		$selected_tagids_array[0] = 1
		$selected_tagids_array[1] = $selected_tagids
		_Log($selected_tagids_array[0] & ' markierter Eintrag ermittelt: ' & $selected_tagids, 1)
	EndIf
	If IsArray($selected_tagids_array) Then
		Return (True)
	Else
		_Log('Error: Fehler bei Erstellung des TagID-Arrays selektierter Einträge', 1)
		Return (False)
	EndIf
EndFunc   ;==>ListViewGetCategories

Func ListViewSelectCategories($xnview_db_file_tags_array)
	_Log('Markiere Kategorien...')
	If Not IsArray($xnview_db_file_tags_array) Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	; Items suchen und markieren
	_GUICtrlListView_BeginUpdate(GUICtrlGetHandle($gui_xnview_listview))
	$count = _GUICtrlListView_GetItemCount(GUICtrlGetHandle($gui_xnview_listview))
	For $c = 0 To $count
		$text = _GUICtrlListView_GetItemText(GUICtrlGetHandle($gui_xnview_listview),$c,1) ; TagIDs aller ListView-Einträge durchsuchen
		For $c_match = 0 To UBound($xnview_db_file_tags_array)-1 ; Jeden Listview-Eintrag mit Array gesuchter TagIDs abgleichen
			If StringCompare($text,$xnview_db_file_tags_array[$c_match])= 0 Then ; Wenn es mit der gesuchten TagID übereinstimmt, diesen Eintrag markieren
				_GUICtrlListView_SetItemChecked(GUICtrlGetHandle($gui_xnview_listview),$c,True)
			EndIf
		Next
	Next
	_GUICtrlListView_EndUpdate(GUICtrlGetHandle($gui_xnview_listview))

	Return(True)
EndFunc

Func ListViewClearCategories()
	_Log('Setze Kategorien im Listview zurück...')
	; Alle Items demarkieren
	_GUICtrlListView_BeginUpdate(GUICtrlGetHandle($gui_xnview_listview))
	$count = _GUICtrlListView_GetItemCount(GUICtrlGetHandle($gui_xnview_listview))
	For $c = 0 To $count
		_GUICtrlListView_SetItemChecked(GUICtrlGetHandle($gui_xnview_listview),$c,False)
	Next
	_GUICtrlListView_EndUpdate(GUICtrlGetHandle($gui_xnview_listview))
EndFunc

Func DB_GetCategoriesCount() ; Anzahl an Kategorien auslesen und Array entsprechender Größe erstellen
	_Log('Datenbank - Lese Anzahl von Kategorien aus...')
	_SQLite($xnview_db_path,1,0)
	_SQLite_Query(-1, "select count(*) from tags;", $hQuery)
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		Global $xnview_db_tagtree_array[$aRow[0]][3]
	WEnd
	_SQLite($xnview_db_path,0,0)
	If Not IsArray($xnview_db_tagtree_array) Then
		_Log('Error: Code: ' & @error, 1)
		Return (False)
	Else
		_Log('Erfolg. ' & UBound($xnview_db_tagtree_array) & ' Kategorien gefunden', 1)
		Return (True)
	EndIf
EndFunc   ;==>DB_GetCategoriesCount

Func DB_GetCategoriesTree() ; Kategorie-Liste auslesen (Label / ID / ParentID) und in Array eintragen
	_Log('Datenbank - Lese Kategorien aus...')
	_SQLite($xnview_db_path,1,0)
	_SQLite_Query(-1, "select tagid, label, parentid, id from tags;", $hQuery)
	$c = 0
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		$xnview_db_tagtree_array[$c][0] = $aRow[1]
		$xnview_db_tagtree_array[$c][1] = $aRow[0]
		$xnview_db_tagtree_array[$c][2] = $aRow[2]
		$c += 1
	WEnd
	_SQLite($xnview_db_path,0,0)
	If Not IsArray($xnview_db_tagtree_array) Then
		_Log('Error: Code: ' & @error, 1)
		Return (False)
	Else
		_Log('Erfolg.', 1)
		Return (True)
	EndIf
EndFunc   ;==>DB_GetCategoriesTree

Func DB_GetFolderID() ; FolderID für Dateipfad ermitteln
	_Log('Datenbank - Ermittle FolderID...')
	If Not IsArray($input_file_split_array) Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $folder_id = False
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select folderid from folders where pathname = '" & StringReplace($input_file_split_array[0], '\', '/') & "/';", $hQuery)
	If Not @error Then
		While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
			If Not @error Then
				$folder_id = $aRow[0]
			Else
				_Log('Error: Abfangen der FolderID-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
			EndIf
		WEnd
		If $folder_id Then
			_Log('Datenbank - FolderID ermittelt: ' & $folder_id, 1)
		Else
			_Log('Keine FolderID ermittelt.', 1)
		EndIf
	Else
		_Log('Error: Abfrage fehlgeschlagen. Error-Code: ' & @error, 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)
	Return ($folder_id)
EndFunc   ;==>DB_GetFolderID

Func DB_GetImageID($folder_id) ; ImageID ermitteln
	_Log('Datenbank - Ermittle ImageID...')
	If Not $folder_id Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $image_id = False
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select imageid from images where folderid = " & $folder_id & " and filename = '" & StringReplace($input_file_split_array[1],"'","''") & '.' & $input_file_split_array[2] & "';", $hQuery)
	If Not @error Then
		While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
			If Not @error Then
				$image_id = $aRow[0]
			Else
				_Log('Error: Abfangen der ImageID-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
			EndIf
		WEnd
		If $image_id Then
			_Log('Datenbank - ImageID ermittelt: ' & $image_id, 1)
		Else
			_Log('Keine ImageID ermittelt.', 1)
		EndIf
	Else
		_Log('Error: Abfrage fehlgeschlagen. Error-Code: ' & @error, 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)
	Return ($image_id)
EndFunc   ;==>DB_GetImageID

Func DB_GetRatingForFile($image_id)
	_Log('Ermittle Bewertung für aktuelle Datei...')
	If Not $image_id Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Global $rating = False

	; Rating für aktuelle Datei holen
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select rating from images where imageid= " & $image_id & ";", $hQuery)
	If Not @error Then
		While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
			If Not @error Then
				If $aRow[0] >= 0 Then
					$rating = $aRow[0]
				Else
					_Log('Error: Ausgelesenes Rating fehlerhaft: ' & $aRow[0],1)
				EndIf
			Else
				_Log('Error: Abfangen der Bewertungs-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
			EndIf
		WEnd
	Else
		_Log('Error: Abfrage fehlgeschlagen. Error-Code: ' & @error, 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)
	If $rating Then
		_Log('Rating ermittelt: ' & $rating,1)
		Return(True)
	Else
		Return(False)
	EndIf
EndFunc

Func DB_GetCategoriesForFile($image_id)
	_Log('Ermittle Kategorien für aktuelle Datei...')
	If Not $image_id Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $xnview_db_file_tags_count
	Local $xnview_db_file_tags_array = False

	_SQLite($xnview_db_path, 1, 0)
	; Ermitteln, wieviele Tags der Datei zugeordnet sind
	_SQLite_Query(-1, "select count(*) from tagstree where imageid=" & $image_id & ";", $hQuery)
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		If Not @error Then
			$xnview_db_file_tags_count = $aRow[0]
		Else
			_Log('Error: Abfangen der Tags-Count-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
		EndIf
	WEnd
	_SQLite($xnview_db_path, 0, 0)

	; Array der Größe des Counts erstellen
	If $xnview_db_file_tags_count Then
		If $xnview_db_file_tags_count > 0 Then
			Local $xnview_db_file_tags_array[$xnview_db_file_tags_count]
			_Log($xnview_db_file_tags_count & ' gesetzte Kategorien für aktuelle Datei gefunden.', 1)
		Else
			_Log('Es liegen keine Kategorien für aktuelle Datei vor', 1)
			Return (False)
		EndIf
	Else
		Return (False)
	EndIf

	; Gefundene Kategorien in Array eintragen
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select tagid from tagstree where imageid=" & $image_id & ";", $hQuery)
	$c = 0
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		If Not @error Then
			$xnview_db_file_tags_array[$c] = $aRow[0]
		Else
			$xnview_db_file_tags_array = False
			_Log('Error: Abfangen der Tags-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
		EndIf
		$c += 1
	WEnd
	_SQLite($xnview_db_path, 0, 0)
	If Not IsArray($xnview_db_file_tags_array) Then
		_Log('Error: Kann Tags nicht ermitteln. Code: ' & @error, 1)
		Return (False)
	Else
		_Log('Kategorien erfolgreich ermittelt', 1)
		Return($xnview_db_file_tags_array)
	EndIf
EndFunc   ;==>DB_GetCategoriesForFile

Func DB_CreateFolderID()
	_Log('Datenbank - Erstelle neue FolderID...')
	If Not IsArray($input_file_split_array) Or Not $input_file_path Then
		_Log('Error: Es fehlen Variablen')
		Return(False)
	EndIf

	Local $folder_id = False

	; Index für neuen FolderID-Eintrag ermitteln
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select max(folderid) from folders;", $hQuery)
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		If Not @error Then
			$folder_id = $aRow[0] + 1
		Else
			_Log('Error: Abfangen der FolderID-Index-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
		EndIf
	WEnd
	; Neue FolderID mitzugehörigem Pfad eintragen
	If $folder_id Then
		_Log('Datenbank - Neuen FolderID-Index erfolgreich ermittelt: ' & $folder_id, 1)
		_SQLite_Exec(-1, "insert into folders(folderid,pathname) values(" & $folder_id & ",'" & StringReplace($input_file_split_array[0], '\', '/') & "/');")
		If Not @error Then
			_Log('FolderID erfolgreich erstellt', 1)
		Else
			_Log('Error: FolderID kann nicht erstellt werden. Error-Code: ' & @error, 1)
		EndIf
	Else
		_Log('Error: Kann Index für neue FolderID nicht ermitteln.', 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)

	Return ($folder_id)
EndFunc   ;==>DB_CreateFolderID

Func DB_CreateImageID($folder_id)
	_Log('Datenbank - Erstelle neue ImageID...')
	If Not $folder_id Or Not IsArray($input_file_split_array) Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $image_id = False

	; ImageID erstellen
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Query(-1, "select max(imageid) from images;", $hQuery)
	While _SQLite_FetchData($hQuery, $aRow) = $SQLITE_OK
		If Not @error Then
			$image_id = $aRow[0] + 1
		Else
			_Log('Error: Abfangen der ImageID-Index-Daten fehlgeschlagen. Error-Code: ' & @error, 1)
		EndIf
	WEnd
	; Neue ImageID mit allen relevanten Daten eintragen
	If $image_id Then
		_Log('Datenbank - Neuen ImageID-Index erfolgreich ermittelt: ' & $image_id, 1)
		_SQLite_Exec(-1, "insert into images(imageid,folderID,filename,size,modifieddate) values(" & $image_id & "," & $folder_id & ",'" & StringReplace($input_file_split_array[1],"'","''") & '.' & $input_file_split_array[2] & "',0,0);")
		If Not @error Then
			_Log('ImageID erfolgreich erstellt', 1)
		Else
			_Log('Error: ImageID kann nicht erstellt werden. Error-Code: ' & @error, 1)
		EndIf
	Else
		_Log('Error: Kann Index für neue ImageID nicht ermitteln.', 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)

	Return ($image_id)
EndFunc   ;==>DB_CreateImageID

Func DB_SetRating($folder_id, $image_id)
	_Log('Datenbank - Update Rating...')
	If Not $image_id Or Not $folder_id Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $return = False

	; Rating updaten
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Exec(-1, "update images set rating=" & $rating & " where imageid=" & $image_id & " and folderid=" & $folder_id & ";")
	If Not @error Then
		_Log('Rating erfolgreich auf ' & $rating & ' geupdated für ImageID: ' & $image_id & ', FolderID: ' & $folder_id, 1)
		$return = True
	Else
		_Log('Error: Kann Rating nicht auf ' & $rating & ' updaten für ImageID: ' & $image_id & ', FolderID: ' & $folder_id & '. Error-Code: ' & @error, 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)

	Return ($return)
EndFunc   ;==>DB_SetRating

Func DB_SetCategories($image_id)
	_Log('Datenbank - Update Kategorien...')
	If Not $image_id Or Not IsArray($selected_tagids_array) Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $return = True

	; Kategorien updaten
	_SQLite($xnview_db_path, 1, 0)
	For $c = 1 To $selected_tagids_array[0]
		_SQLite_Exec(-1, "insert into tagstree(imageid,tagid) values(" & $image_id & "," & $selected_tagids_array[$c] & ");")
		If @error Then
			$return = False
			_Log('Error: Kann Kategorie nicht updaten für ImageID: ' & $image_id & '. Error-Code: ' & @error, 1)
		EndIf
	Next
	_SQLite($xnview_db_path, 0, 0)

	If $return Then _Log('Kategorien erfolgreich geupdated.', 1)

	Return ($return)
EndFunc   ;==>DB_SetCategories

Func DB_DeleteCategories($image_id)
	_Log('Datenbank - Entferne Kategorien...')
	If Not $image_id Then
		_Log('Error: Es fehlen Variablen.', 1)
		Return (False)
	EndIf

	Local $return = True

	; Kategorien entfernen
	_SQLite($xnview_db_path, 1, 0)
	_SQLite_Exec(-1, "delete from tagstree where imageid = " & $image_id & ";")
	If @error Then
		$return = False
		_Log('Error: Kann Kategorien nicht entfernen. ImageID: ' & $image_id & '. Error-Code: ' & @error, 1)
	EndIf
	_SQLite($xnview_db_path, 0, 0)

	If $return Then _Log('Kategorien erfolgreich entfernt', 1)

	Return ($return)
EndFunc   ;==>DB_DeleteCategories

Func WM_NOTIFY($hWnd, $Msg, $wParam, $lParam)
	Local $tNMHDR, $hWndFrom, $iCode

	$tNMHDR = DllStructCreate($tagNMHDR, $lParam)
	$hWndFrom = DllStructGetData($tNMHDR, "hWndFrom")
	$iCode = DllStructGetData($tNMHDR, "Code")

	$gui_xnview_listview_hwnd = GUICtrlGetHandle($gui_xnview_listview)
	Switch $hWndFrom
		Case $gui_xnview_listview_hwnd
			Switch $iCode
				Case $NM_CUSTOMDRAW
					Local $tCustDraw = DllStructCreate('hwnd hwndFrom;int idFrom;int code;' & _
							'dword DrawStage;hwnd hdc;long rect[4];dword ItemSpec;int ItemState;dword Itemlparam;' & _
							'dword clrText;dword clrTextBk;int SubItem;' & _
							'dword ItemType;dword clrFace;int IconEffect;int IconPhase;int PartID;int StateID;long rectText[4];int Align', _ ;winxp or later
							$lParam)
					Local $iDrawStage = DllStructGetData($tCustDraw, 'DrawStage')
					If $iDrawStage = $CDDS_PREPAINT Then Return $CDRF_NOTIFYITEMDRAW

					Local $iItem = DllStructGetData($tCustDraw, 'ItemSpec')

					; Wenn Hauptkategorie, dann Schrift Fett
					$text = _GUICtrlListView_GetItemText(GUICtrlGetHandle($gui_xnview_listview), $iItem, 2)
					If $text = -1 Then
						; Wenn Kategorie selektiert ist, dann Schrift farbig
						$check = _GUICtrlListView_GetItemChecked(GUICtrlGetHandle($gui_xnview_listview), $iItem)
						If $check Then
							DllStructSetData($tCustDraw, 'clrText', 0x0000ff)
							Local $hDC = DllStructGetData($tCustDraw, "hdc")
							_WinAPI_SelectObject($hDC, $font_bold)
							Return $CDRF_NEWFONT
						Else
							DllStructSetData($tCustDraw, 'clrText', 0x000000)
							Local $hDC = DllStructGetData($tCustDraw, "hdc")
							_WinAPI_SelectObject($hDC, $font_bold)
							Return $CDRF_NEWFONT
						EndIf
					Else ; Subkategorien normal
						; Wenn Kategorie selektiert ist, dann Schrift farbig
						$check = _GUICtrlListView_GetItemChecked(GUICtrlGetHandle($gui_xnview_listview), $iItem)
						If $check Then
							DllStructSetData($tCustDraw, 'clrText', 0x0000ff)
							Local $hDC = DllStructGetData($tCustDraw, "hdc")
							_WinAPI_SelectObject($hDC, $font_normal)
							Return $CDRF_NEWFONT
						Else
							DllStructSetData($tCustDraw, 'clrText', 0x000000)
							Local $hDC = DllStructGetData($tCustDraw, "hdc")
							_WinAPI_SelectObject($hDC, $font_normal)
							Return $CDRF_NEWFONT
						EndIf
					EndIf



			EndSwitch
	EndSwitch

	Return $GUI_RUNDEFMSG
EndFunc   ;==>WM_NOTIFY

Func Quit($gui_xnview_form)
	_Log('---', 'BEENDE SCRIPT')
	_SQLite($xnview_db_path,0,0)
	_SavePosToIni($gui_xnview_form, $ini_section)
	_WinAPI_DeleteObject($font_bold)
	_WinAPI_DeleteObject($font_normal)
	_Log('Ende.', 1)
	Exit
EndFunc   ;==>Quit





; GEKLAUT (Kontextmenü für Opt-Button)

; Show a menu in a given GUI window which belongs to a given GUI ctrl
Func ShowMenu($hWnd, $CtrlID, $nContextID)
	Local $arPos, $x, $y
	Local $hMenu = GUICtrlGetHandle($nContextID)

	$arPos = ControlGetPos($hWnd, "", $CtrlID)

	$x = $arPos[0]
	$y = $arPos[1] + $arPos[3]

	ClientToScreen($hWnd, $x, $y)
	TrackPopupMenu($hWnd, $hMenu, $x, $y)
EndFunc   ;==>ShowMenu

; Convert the client (GUI) coordinates to screen (desktop) coordinates
Func ClientToScreen($hWnd, ByRef $x, ByRef $y)
	Local $stPoint = DllStructCreate("int;int")

	DllStructSetData($stPoint, 1, $x)
	DllStructSetData($stPoint, 2, $y)

	DllCall("user32.dll", "int", "ClientToScreen", "hwnd", $hWnd, "ptr", DllStructGetPtr($stPoint))

	$x = DllStructGetData($stPoint, 1)
	$y = DllStructGetData($stPoint, 2)
	; release Struct not really needed as it is a local
	$stPoint = 0
EndFunc   ;==>ClientToScreen

; Show at the given coordinates (x, y) the popup menu (hMenu) which belongs to a given GUI window (hWnd)
Func TrackPopupMenu($hWnd, $hMenu, $x, $y)
	DllCall("user32.dll", "int", "TrackPopupMenuEx", "hwnd", $hMenu, "int", 0, "int", $x, "int", $y, "hwnd", $hWnd, "ptr", 0)
EndFunc   ;==>TrackPopupMenu

;==> GEKLAUT
