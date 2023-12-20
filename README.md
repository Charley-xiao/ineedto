# INeedTo: A simple to-do list app based on Flask

## Run the app

Edit the configurations in `config.py` if necessary. Specifically, in the field `smtp`, you need to fill in the email address and password of the sender. The email address will be used to send the verification code to the user when they register. The password is the password or API key of the email address.

Then, run the following command to run the app:

```
python app.py
```

or

```
python app.py --host <host> --port <port>
```

## Check database

To check the database, run the following command, as it displays the content of the database in the terminal:

```
python disp_db.py
```

## Test the app

To test the app, access the login page or register page to create a new account. Then, you can use the account to log in and test the app. Remember that your email address should be valid.

## Contribute

If you want to contribute to this project, please fork this repository and create a pull request. You can also create an issue if you find any bugs or have any suggestions. Thank you!
