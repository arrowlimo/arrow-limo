Attribute VB_Name = "CopyEmailToCharter"
' ========================================
' Arrow Limousine - Copy Email to Charter
' ========================================
' This VBA macro extracts selected email content and copies it to clipboard
' formatted for pasting into charter dispatcher notes
'
' INSTALLATION:
' 1. Open Outlook
' 2. Press ALT+F11 to open VBA Editor
' 3. Insert > Module
' 4. Paste this code
' 5. Tools > References > Check "Microsoft Forms 2.0 Object Library"
' 6. Add button to Quick Access Toolbar or ribbon
'
' USAGE:
' 1. Select an email in Outlook
' 2. Click the "Copy to Charter" button
' 3. Paste (Ctrl+V) into charter dispatcher notes field

Sub CopyEmailToCharterNotes()
    On Error GoTo ErrorHandler
    
    Dim objMail As Outlook.MailItem
    Dim strOutput As String
    Dim objData As DataObject
    
    ' Check if an email is selected
    If Application.ActiveExplorer.Selection.Count = 0 Then
        MsgBox "Please select an email first", vbExclamation, "No Email Selected"
        Exit Sub
    End If
    
    ' Get the selected email
    Set objMail = Application.ActiveExplorer.Selection.Item(1)
    
    ' Extract reserve number from subject if present (format: Re: [012345] or Reserve #012345)
    Dim reserveNumber As String
    reserveNumber = ExtractReserveNumber(objMail.Subject)
    
    ' Format the email content
    strOutput = "================================" & vbCrLf
    strOutput = strOutput & "EMAIL COPIED: " & Format(Now, "yyyy-mm-dd hh:nn AM/PM") & vbCrLf
    
    If reserveNumber <> "" Then
        strOutput = strOutput & "RESERVE #: " & reserveNumber & vbCrLf
    End If
    
    strOutput = strOutput & "================================" & vbCrLf
    strOutput = strOutput & "FROM: " & objMail.SenderName & " <" & objMail.SenderEmailAddress & ">" & vbCrLf
    strOutput = strOutput & "DATE: " & Format(objMail.ReceivedTime, "yyyy-mm-dd hh:nn AM/PM") & vbCrLf
    strOutput = strOutput & "SUBJECT: " & objMail.Subject & vbCrLf
    strOutput = strOutput & "--------------------------------" & vbCrLf
    strOutput = strOutput & vbCrLf
    
    ' Get plain text body (strip HTML)
    Dim emailBody As String
    emailBody = objMail.Body
    
    ' Limit to first 2000 characters to avoid clipboard issues
    If Len(emailBody) > 2000 Then
        emailBody = Left(emailBody, 2000) & vbCrLf & vbCrLf & "[...email truncated...]"
    End If
    
    strOutput = strOutput & emailBody & vbCrLf
    strOutput = strOutput & vbCrLf
    strOutput = strOutput & "================================" & vbCrLf & vbCrLf
    
    ' Copy to clipboard
    Set objData = New DataObject
    objData.SetText strOutput
    objData.PutInClipboard
    
    ' Show confirmation
    If reserveNumber <> "" Then
        MsgBox "Email content copied to clipboard for Reserve #" & reserveNumber & vbCrLf & vbCrLf & _
               "Paste (Ctrl+V) into Dispatcher Notes field", vbInformation, "Email Copied"
    Else
        MsgBox "Email content copied to clipboard" & vbCrLf & vbCrLf & _
               "Paste (Ctrl+V) into Dispatcher Notes field", vbInformation, "Email Copied"
    End If
    
    Exit Sub
    
ErrorHandler:
    MsgBox "Error copying email: " & Err.Description, vbCritical, "Error"
End Sub

' ========================================
' Helper Function: Extract Reserve Number
' ========================================
Function ExtractReserveNumber(subjectLine As String) As String
    Dim regEx As Object
    Dim matches As Object
    
    Set regEx = CreateObject("VBScript.RegExp")
    
    ' Match patterns like [012345] or Reserve #012345 or Res#012345
    regEx.Pattern = "\[?(\d{6})\]?|Reserve\s*#?\s*(\d{6})|Res\s*#?\s*(\d{6})"
    regEx.IgnoreCase = True
    regEx.Global = False
    
    Set matches = regEx.Execute(subjectLine)
    
    If matches.Count > 0 Then
        ' Return first captured group that's not empty
        Dim i As Integer
        For i = 1 To matches(0).SubMatches.Count - 1
            If Not IsNull(matches(0).SubMatches(i)) And matches(0).SubMatches(i) <> "" Then
                ExtractReserveNumber = matches(0).SubMatches(i)
                Exit Function
            End If
        Next i
    End If
    
    ExtractReserveNumber = ""
End Function

' ========================================
' OPTIONAL: Direct Database Insert Version
' ========================================
' This version writes directly to the database instead of clipboard
' Requires: Reference to "Microsoft ActiveX Data Objects 6.1 Library"

Sub CopyEmailToCharterDatabase()
    On Error GoTo ErrorHandler
    
    Dim objMail As Outlook.MailItem
    Dim reserveNumber As String
    Dim emailContent As String
    Dim conn As Object
    Dim cmd As Object
    
    ' Check if an email is selected
    If Application.ActiveExplorer.Selection.Count = 0 Then
        MsgBox "Please select an email first", vbExclamation, "No Email Selected"
        Exit Sub
    End If
    
    ' Get the selected email
    Set objMail = Application.ActiveExplorer.Selection.Item(1)
    
    ' Extract reserve number
    reserveNumber = ExtractReserveNumber(objMail.Subject)
    
    If reserveNumber = "" Then
        MsgBox "Could not find reserve number in email subject" & vbCrLf & vbCrLf & _
               "Subject must contain: [012345] or Reserve #012345", vbExclamation, "Reserve Number Required"
        Exit Sub
    End If
    
    ' Format email content
    emailContent = "================================" & vbCrLf
    emailContent = emailContent & "EMAIL: " & Format(Now, "yyyy-mm-dd hh:nn AM/PM") & vbCrLf
    emailContent = emailContent & "FROM: " & objMail.SenderName & " <" & objMail.SenderEmailAddress & ">" & vbCrLf
    emailContent = emailContent & "DATE: " & Format(objMail.ReceivedTime, "yyyy-mm-dd hh:nn AM/PM") & vbCrLf
    emailContent = emailContent & "SUBJECT: " & objMail.Subject & vbCrLf
    emailContent = emailContent & "--------------------------------" & vbCrLf & vbCrLf
    emailContent = emailContent & Left(objMail.Body, 2000) & vbCrLf
    emailContent = emailContent & "================================" & vbCrLf & vbCrLf
    
    ' Connect to database
    Set conn = CreateObject("ADODB.Connection")
    conn.ConnectionString = "Provider=MSDASQL;Driver={PostgreSQL Unicode};Server=localhost;Port=5432;Database=almsdata;Uid=postgres;Pwd=***REMOVED***;"
    conn.Open
    
    ' Append to existing dispatcher_notes
    Set cmd = CreateObject("ADODB.Command")
    cmd.ActiveConnection = conn
    cmd.CommandText = "UPDATE charters SET dispatcher_notes = COALESCE(dispatcher_notes, '') || $1 WHERE reserve_number = $2"
    cmd.Parameters.Append cmd.CreateParameter("@content", 200, 1, Len(emailContent), emailContent)
    cmd.Parameters.Append cmd.CreateParameter("@reserve", 200, 1, 6, reserveNumber)
    cmd.Execute
    
    conn.Close
    
    MsgBox "Email content saved to Reserve #" & reserveNumber & vbCrLf & vbCrLf & _
           "Refresh the charter form to see updated dispatcher notes", vbInformation, "Email Saved"
    
    Exit Sub
    
ErrorHandler:
    MsgBox "Error saving email: " & Err.Description, vbCritical, "Error"
    If Not conn Is Nothing Then
        If conn.State = 1 Then conn.Close
    End If
End Sub
