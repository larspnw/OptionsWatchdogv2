@echo off

set STACKNAME="optionswatchdogv2"

call sam build
if %ERRORLEVEL% NEQ 0 (
    echo !!!!!!!!!! Build Failed
    exit /b
)

call sam package --output-template packaged.yaml --s3-bucket larsbucket1
if %ERRORLEVEL% NEQ 0 (
    echo !!!!!!!!!! Package Failed
    goto :eof
)

call sam deploy --template-file packaged.yaml --region us-east-1 --capabilities CAPABILITY_IAM --stack-name %STACKNAME%
if %ERRORLEVEL% NEQ 0 (
	echo !!!!!!!!!! deploy failed
    exit /b
)

echo SUCCESS for %STACKNAME%
exit /b

